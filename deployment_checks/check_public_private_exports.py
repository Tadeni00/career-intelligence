"""Block tracked personal CV/profile exports in active tree.

Does not rewrite public history. Never log file contents.
"""
from __future__ import annotations

import re
import subprocess

def private_export_path(path: str) -> bool:
    """Detect root-level CV and profile exports, including unexpected variants."""
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("cv/")
        or bool(re.fullmatch(r"cv_text(?:[_-].*)?\.(?:txt|md|json)", normalized, re.I))
        or bool(re.fullmatch(r"val_(?:profile|extraction)[^/]*\.(?:json|txt|pdf|docx)", normalized, re.I))
        or bool(re.fullmatch(r"(?:.*[_-])?(?:resume|curriculum_vitae|personal_cv)[^/]*\.(?:pdf|docx)", normalized, re.I))
    )

def violations(tracked: dict[str, str]) -> list[str]:
    return [
        f"Tracked private-export location: {path}"
        for path in tracked
        if private_export_path(path)
    ]


def tracked_blobs() -> dict[str, str]:
    # Git index, not local .gitignore status: detects staged/tracked files.
    data = subprocess.run(
        ["git", "ls-files", "-s", "-z"], check=True, capture_output=True
    ).stdout
    tracked: dict[str, str] = {}
    for item in data.split(b"\0"):
        if not item:
            continue
        header, raw_path = item.split(b"\t", 1)
        sha = header.split()[1].decode("ascii")
        tracked[raw_path.decode("utf-8", errors="replace")] = sha
    return tracked

if __name__ == "__main__":
    findings = violations(tracked_blobs())
    for finding in findings:
        print("PRIVACY-GATE:", finding)
    if findings:
        raise SystemExit("Public repository export safety gate failed. See SEC-003.")
    print("Public export active-tree check passed (historical SEC-003 exposure remains unresolved).")
