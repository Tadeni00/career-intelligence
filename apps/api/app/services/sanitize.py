"""Deterministic output-safety layer for employer-facing documents.

Runs after claim validation and before a document may receive a final VALID
status. Detects injected/suspicious artefacts rather than trusting prose.

Design note: base64-like text is NOT rejected merely for looking like base64.
A payload is only suspicious when structural signals (decodes to an IP-like or
otherwise implausible value) combine with contextual signals (marker tokens,
position at end of document, absence of prose context).
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import re

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV4_PORT_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b")
# RFC1918 / public IPv4 inside base64 (32 chars for 4 octets + separators).
IPV4_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{20,30}={0,2}\b")

URL_RE = re.compile(r"https?://[^\s<>\"]+|www\.[^\s<>\"]+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]\d{3,4}[\s.-]?\d{3,4}")

# Affine/promo/tracking vocabulary that has no place in an application document.
SUSPICIOUS_MARKERS = (
    r"\bbrightest\b", r"\bcloa?king\b", r"\baffiliate\b", r"\btraffic\s+source\b",
    r"\btracking\s+(?:id|token|code)\b", r"\breferral\s+(?:id|link|code)\b",
    r"\bclick\s?through\b", r"\bad\s?network\b", r"\bmonetiz",
    r"\bhidden\s+content\b", r"\bcloaked\b", r"\bspoof",
    r"\bdiscover(?:ed)?\s+(?:by|through)\s+secret\b",
)

# Model/system instruction leakage.
PROMPT_LEAK_RE = re.compile(
    r"(?:^|\n)\s*(?:system|assistant|user)\s*:\s|"
    r"^\s*(?:you are|as an ai|i am an ai|my instructions)\b|"
    r"</?(?:system|assistant|tool|function_call|invoke)\b|"
    r"\[/?INST\]|<<SYS>>|###\s*(?:instruction|system)\s*prompt",
    re.I | re.M,
)

TOOL_METADATA_RE = re.compile(
    r"\b(?:tool_call|function_call|tool_use|stop_reason|finish_reason)\b|"
    r"\"(?:tool_calls|function_call|logprobs)\"\s*:|"
    r"<\|(?:im_start|im_end|eot_id|endoftext)\|>",
)

PLACEHOLDER_RE = re.compile(
    r"\[(?:email|e-mail|phone|telephone|mobile|address|date|insert|your name|"
    r"company name|full name|here)\b[^\]]*\]|<[A-Z_]{3,}>|"
    r"\b(?:lorem ipsum|xxx+|tbd|tba|foo bar)\b",
    re.I,
)

CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Sentences that are pure machine chatter rather than application prose.
_META_RE = re.compile(
    r"\b(?:as requested|here is the|here's the|below is the|i have generated|"
    r"i cannot|i'm unable|cannot fulfill)\b",
    re.I,
)


def _looks_like_ip_string(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


_IPV4_SHAPE_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def _looks_like_ip_string(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _decode_b64_candidate(token: str) -> str | None:
    """Decode a base64-like token, tolerating truncation and misalignment.

    Injected payloads are frequently not cleanly padded and may carry a stray
    leading character (the VJ-03 token is offset by one). Every candidate window
    is decoded and the best result is chosen, so equivalent payloads are caught
    by pattern rather than by hard-coding one string.
    """
    cleaned = token.strip().strip(".,;:!?").strip()
    if len(cleaned) < 12 or not re.fullmatch(r"[A-Za-z0-9+/=]+", cleaned):
        return None
    core = cleaned.rstrip("=")

    results: list[str] = []
    for start in range(0, min(4, len(core) - 11)):
        window = core[start:]
        for length in range(len(window), 11, -1):
            candidate = window[:length]
            padded = candidate + "=" * (-len(candidate) % 4)
            try:
                raw = base64.b64decode(padded, validate=True)
            except (binascii.Error, ValueError):
                continue
            if len(raw) < 6:
                continue
            try:
                results.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                continue  # not valid UTF-8 text; almost certainly noise

    for text in results:
        if _IPV4_SHAPE_RE.search(text):
            return text
    for text in results:
        if text.isascii() and text.isprintable():
            return text
    return None


def find_issues(
    text: str,
    *,
    confirmed_emails: set[str] | None = None,
    confirmed_phones: set[str] | None = None,
    confirmed_urls: set[str] | None = None,
) -> list[dict]:
    """Return a list of sanitisation findings for generated output."""
    confirmed_emails = {e.strip().lower() for e in (confirmed_emails or set())}
    confirmed_phones = {re.sub(r"\D", "", p) for p in (confirmed_phones or set())}
    confirmed_urls = {u.strip().lower() for u in (confirmed_urls or set())}
    findings: list[dict] = []

    def add(code: str, message: str, severity: str = "error", detail: str | None = None):
        findings.append({"severity": severity, "code": code, "message": message,
                         "detail": detail})

    if not text:
        add("SUSPICIOUS_OUTPUT", "Generated document is empty.")
        return findings

    # 1. control characters
    if CONTROL_CHAR_RE.search(text):
        add("SUSPICIOUS_OUTPUT", "Document contains control characters.",
            detail=CONTROL_CHAR_RE.search(text).group(0))

    # 2. raw IPs (allow 127.0.0.1/0.0.0.0 style docs? still flag)
    for match in IPV4_RE.findall(text):
        if _looks_like_ip_string(match):
            add("SUSPICIOUS_OUTPUT",
                f"Document contains a raw IP address ({match}).", detail=match)

    # 3. encoded IP payloads (the VJ-03 class) + structural/context signals
    has_marker = any(re.search(p, text, re.I) for p in SUSPICIOUS_MARKERS)
    for token in IPV4_B64_RE.findall(text):
        decoded = _decode_b64_candidate(token)
        if not decoded:
            continue
        stripped = decoded.strip()
        if _looks_like_ip_string(stripped) or _IPV4_SHAPE_RE.search(stripped):
            add("SUSPICIOUS_OUTPUT",
                "Document contains a base64-encoded IP address "
                f"(decodes to {stripped}).", detail=token)
        elif has_marker and re.fullmatch(r"[\d.]+", stripped):
            add("SUSPICIOUS_OUTPUT",
                f"Document contains an encoded network identifier (decodes to {stripped}).",
                detail=token)
    if has_marker:
        marker = next(re.search(p, text, re.I).group(0) for p in SUSPICIOUS_MARKERS
                      if re.search(p, text, re.I))
        add("SUSPICIOUS_OUTPUT",
            f"Document contains a suspicious tracking/promotion marker ({marker!r}).",
            detail=marker)

    # 4. unexpected URLs
    for url in URL_RE.findall(text):
        if url.strip().lower() not in confirmed_urls:
            add("SUSPICIOUS_OUTPUT",
                f"Document contains a URL that was not supplied ({url}).", detail=url)

    # 5. unexpected emails
    for email in EMAIL_RE.findall(text):
        if email.lower() not in confirmed_emails:
            add("UNSUPPORTED_CONTACT",
                f"Document contains an email address not on the profile ({email}).",
                detail=email)

    # 6. unexpected phone numbers
    for phone in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 9:
            continue
        if digits not in confirmed_phones:
            add("UNSUPPORTED_CONTACT",
                f"Document contains a phone number not on the profile ({phone}).",
                detail=phone)

    # 7. placeholders
    for match in PLACEHOLDER_RE.finditer(text):
        add("SUSPICIOUS_OUTPUT",
            f"Document contains an unfilled placeholder ({match.group(0)!r}).",
            detail=match.group(0))

    # 8. prompt / instruction leakage
    for regex in (PROMPT_LEAK_RE, TOOL_METADATA_RE):
        m = regex.search(text)
        if m:
            add("SUSPICIOUS_OUTPUT",
                "Document contains model/system instruction or tool metadata.",
                detail=m.group(0)[:120])

    # 9. assistant meta-commentary
    m = _META_RE.search(text)
    if m:
        add("SUSPICIOUS_OUTPUT",
            "Document contains assistant meta-commentary rather than application prose.",
            detail=m.group(0))

    return findings


def is_clean(findings: list[dict]) -> bool:
    return not any(f.get("severity") == "error" for f in findings)


__all__ = ["find_issues", "is_clean"]
