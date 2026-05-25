# Issue Classification Prompt v1

Classify issue inputs into strict schema fields only:
work_type, scope, risk, planning_priority, triage_urgency, lifecycle_status,
affected_areas, needs_maintainer_input, classification_confidence,
classification_prompt_version, classification_input_hash.

Use evidence from issue title/body/labels/state only and keep output deterministic.
Do not propose external writes.
