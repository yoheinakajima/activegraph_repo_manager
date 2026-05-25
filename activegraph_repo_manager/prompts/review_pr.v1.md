# review_pr.v1

Replay-only PR review prompt contract.

- Emit structured `ReviewFinding` records only.
- Every finding must include concrete `evidence_refs`.
- Keep outputs schema-valid for required fields and enum-like values.
- Do not perform or request external writes/actions.
