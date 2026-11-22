# CI-002 — V3.3 frozen-artifact line-ending reconciliation

**Scope:** read-only verification of an initial GitHub import. This note does not authorize research execution or modify the experimental corpus, generated results, model configuration, or governance decisions.

## Incident and direct evidence

The initial CI-002 workflow ([run 45038192050](https://github.com/Tadeni00/career-intelligence/actions/runs/45038192050)) reported 888 passed, 1 skipped, 2 failed. Both failures were SHA-256 byte assertions in `tests/test_v33_final_analysis.py`. The original expected digests are independently present in the V3.3 analysis documentation.

The read-only fingerprint probe in [run 45039528251](https://github.com/Tadeni00/career-intelligence/actions/runs/45039528251) proved that **CRLF-only reconstruction of the committed LF files exactly reproduces the original expected hashes**:

| Artifact | SHA-256 of initial Git LF bytes | SHA-256 after changing LF to CRLF (historical) |
| --- | --- | --- |
| `docs/benchmark/v3_3c_extraction_reproducibility_runs.json` | `9badf91c013f440629c13c5cf051a3be9de30af3516aa5a255a0fcc0db4ae92d` | `6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0` |
| `docs/benchmark/matching_benchmark_v3.json` | `06356fffd260ab449562de1bc1f4ff45b37b00d244a6149b02bd01973cf8452f` | `4199f5d386e1fb8b9be1a6c053c0c9cc6f2e6e8afeadc31112e650c34f37345f` |

Both initial Git files have zero CRLF pairs, contain only LF newlines and have no final newline. Their JSON parses successfully. Both files were present in the repository's initial commit `da4259286d776b6d22fe299a84f993c47e783f9b`. The PR made no changes to these artifacts.

## Conclusion and test contract

The observed checksum mismatches are fully explained by newline representation: the committed LF bytes correspond exactly to the historically hashed CRLF bytes, with no other byte changes in those two artifacts. The evidence does **not** establish which tool introduced newline conversion at import; it establishes the equivalence of these two concrete byte sequences.

`tests/test_v33_final_analysis.py` now pins **both** original Git LF digests and historical CRLF digests. For each artifact it checks the exact LF hash, absence of carriage returns and trailing newline, and the exact historical digest from newline-only reconstruction. This is stricter than simply updating the expected hash to the new value or comparing parsed JSON, and requires no file rewrite.

`deployment_checks/frozen_artifact_probe.py` provides independent read-only fingerprint reporting. It does not touch either artifact.

## Scope boundary

- No frozen artifacts, human labels, provenance archives, benchmark membership, or V3.4 experimental controls were changed.
- This finding addresses **byte integrity only**. It does not establish correctness, semantic support of extracted requirements, recommendation quality, or authorization to run adjudication.
- All additional CI failures, if any, must be investigated separately; do not treat this document as a general waiver.
