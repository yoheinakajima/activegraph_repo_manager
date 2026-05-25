# planning_decider.v1

Emit deterministic, schema-valid `PlanningPatchProposal` objects only.

Requirements:
- Output must be approval-gated proposal data only; never mutate `PlanningItem` directly.
- Include evidence-backed rationale with explicit evidence refs.
- Respect bounded enums for `status` and `change_type`.
- Include target external key or target slug plus from/to values.
- Include `proposed_item` only for `change_type = new_item`.
- Do not perform or suggest external writes (GitHub, files, comments, labels, review actions).
- Keep outputs fixture-replayable; tests do not require live LLM calls.
