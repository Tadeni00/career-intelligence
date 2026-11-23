"""Fail CI if public-tracked personal exports expand or change silently.

This is a containment gate, NOT remediation of existing public files/history.
Never print private file content. Approved legacy Git blob IDs are not evidence
that their contents are safe to share.
"""
from __future__ import annotations

import re
import subprocess

# Explicitly grandfathered for detection only; SEC-003 requires removal
# through a separate owner-approved remediation plan.
LEGACY_BLOBS = {
    "cv/Tomisin_Adeniyi_ML_Engineer.pdf": "c14a83b1905b9e0cb1db336bf7e8dd2f7a7bd009",
    "cv_text.txt": "08e5c09d43c18a440d5254282e80520287020fad",
    "val_extraction.json": "71d3ab5019e248e7cc35d775e1755d1e6bda5ebb",
    "val_profile.json": "1aab0aec5aa0a7c24494badfa0f10fa48691d706",
    "val_profile_fixed.json": "5bdb48ae7de9456f73f681bb47f1404307abdebc",
}

def private_export_path(path: str) -> bool:
    """Detect root-level CV and profile exports, including unexpected variants."""
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("cv/")
        or bool(re.fullmatch(r"cv_text(?:[_-].*)?\\.(?:txt|md|json)", normalized, re.I))
        or bool(re.fullmatch(r"val_(?:profile|extraction)[^/]*\\.(?:json|txt|pdf|docx)", normalized, re.I))
        or bool(re.fullmatch(r"(?:.*[_-])?(?:resume|curriculum_vitae|personal_cv)[^/]*\\.(?:pdf|docx)", normalized, re.I))
    )

def violations(tracked: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for path, sha in tracked.items():
        if not private_export_path(path):
            continue
        allowed = LEGACY_BLOBS.get(path)
        if allowed is None:
            problems.append(f"New tracked private-export location: {path}")
        elif sha != allowed:
            problems.append(f"Grandfathered private-export blob changed: {path}")
    return problems

def tracked_blobs() -> dict[str, str]:
    # Git index, not local .gitignore status: detects staged/tracked files.
    data = subprocess.run(
        ["git", "ls-files", "-s", "-z"], check=True, capture_output=True
    ).stdout
    tracked: dict[str, str] = {}
    for item in data.split(b"\\0"):
        if not item:
            continue
        header, raw_path = item.split(b"\\t", 1)
        sha = header.split()[1].decode("ascii")
        tracked[raw_path.decode("utf-8", errors="replace")] = sha
    return tracked

if __name__ == "__main__":
    findings = violations(tracked_blobs())
    for finding in findings:
        print("PRIVACY-GATE:", finding)
    if findings:
        raise SystemExit("Public repository export safety gate failed. See SEC-003.")
    print("Public export containment check passed (existing SEC-003 exposure remains unresolved).")
