# Acceptance criteria

Phase-by-phase done conditions emphasize idempotent ingest, deterministic behaviors, strict schema validation, replay stability, and approval-gated actions.

## Phase 5a gate (hardening)

Phase 5a supports `ExternalActionProposal` generation and dry-run execution only. No real GitHub or filesystem writes are allowed in Phase 5a. Phase 5b must explicitly add live-write tools, approval checks, and tests proving denied/rejected actions cannot execute. Until Phase 5b, all external actions remain helper-level dry-run only.
