# PR Classification Prompt v1

Classify pull request inputs into strict schema fields only:
work_type, scope, risk, planning_priority, triage_urgency, lifecycle_status,
affected_areas, needs_maintainer_input, classification_confidence,
classification_prompt_version, classification_input_hash.

Use evidence from PR title/body/labels/state/head_sha/changed files only and keep output deterministic.
Do not propose external writes.
