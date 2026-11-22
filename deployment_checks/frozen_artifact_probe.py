"""Read-only byte-integrity diagnostics for two frozen V3.3 research artifacts.

No file writes, network access or provider calls. Does not update expected hashes.
The report distinguishes byte differences from candidate newline/serialization changes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        "docs/benchmark/v3_3c_extraction_reproducibility_runs.json",
        "6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0",
    ),
    (
        "docs/benchmark/matching_benchmark_v3.json",
        "4199f5d386e1",
    ),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def report(path: Path, expected: str) -> dict[str, object]:
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf
    lone_cr = raw.count(b"\r") - crlf
    candidates = {
        "as_committed": raw,
        "lf_normalized": raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"),
        "crlf_normalized": raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n"),
        "one_final_lf": raw.rstrip(b"\r\n") + b"\n",
        "no_final_newline": raw.rstrip(b"\r\n"),
    }
    try:
        value = json.loads(raw)
        parsed = True
        candidates["canonical_json_sorted"] = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        candidates["pretty_json_two_space"] = json.dumps(
            value, ensure_ascii=False, indent=2
        ).encode("utf-8")
        candidates["pretty_json_two_space_lf"] = candidates["pretty_json_two_space"] + b"\n"
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = False
    digests = {name: sha256(data) for name, data in candidates.items()}
    return {
        "path": str(path.relative_to(ROOT)),
        "byte_length": len(raw),
        "json_parses": parsed,
        "crlf_pairs": crlf,
        "lone_lf": lone_lf,
        "lone_cr": lone_cr,
        "ends_with_lf": raw.endswith(b"\n"),
        "expected_sha_or_prefix": expected,
        "actual_sha256": digests["as_committed"],
        "matches_expected_as_committed": digests["as_committed"].startswith(expected),
        "variants_matching_expected": [
            key for key, value in digests.items() if value.startswith(expected)
        ],
        "variant_digests": digests,
    }


def main() -> None:
    # Print only metadata/digests, never artifact contents or candidate information.
    for relative, expected in ARTIFACTS:
        print(json.dumps(report(ROOT / relative, expected), indent=2))


if __name__ == "__main__":
    main()
