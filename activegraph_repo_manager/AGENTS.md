# activegraph_repo_manager/AGENTS.md

Before editing package files, read:
- `docs/codex/project_brief.md`
- `docs/codex/phase_plan.md`
- `docs/codex/activegraph_pack_contract.md`

Rules:
- Use pack-aware decorators/imports.
- Do not globally register behaviors or tools at import time.
- Keep object schemas strict.
- Prefer Pydantic enums over freeform strings.
- Preserve replayability and fixture-based tests.
- Keep MVP scope tight.
