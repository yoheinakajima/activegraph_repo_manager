# AGENTS.md — ActiveGraph repo manager

## Mission

We are building `activegraph_repo_manager`, an auditable repo-governance pack for the ActiveGraph repository.

The first version is a read-only MVP:
- mirror repo, issue, PR, and planning-doc state
- index repo files, symbols, and tests
- classify issues and PRs
- emit structured PR review findings

Later versions may propose planning updates and GitHub actions, but only behind approval gates.

This is not an autonomous maintainer. Use the phrase “repo-governance pack,” not “self-managing AI maintainer.”

## Before coding

For any non-trivial task, start with a short plan.

Read these first:
1. `docs/codex/project_brief.md`
2. `docs/codex/phase_plan.md`
3. `docs/codex/acceptance_criteria.md`

Then read the file-specific docs below.

## Routing table

When editing `activegraph_repo_manager/schemas.py`:
- read `docs/codex/ontology.md`
- read `docs/codex/external_keys.md`

When editing `activegraph_repo_manager/pack.py`, `settings.py`, `relations.py`, or `policies.py`:
- read `docs/codex/activegraph_pack_contract.md`
- read `docs/codex/governance_policy.md`

When editing `activegraph_repo_manager/behaviors/**`:
- read `docs/codex/behavior_contract.md`
- read `docs/codex/pattern_contract.md`
- read `docs/codex/governance_policy.md`
- read `docs/codex/external_keys.md`

When editing `activegraph_repo_manager/tools/**`:
- read `docs/codex/fixture_contract.md`
- read `docs/codex/external_keys.md`

When editing `activegraph_repo_manager/prompts/**`:
- read `docs/codex/prompt_versioning.md`
- read `docs/codex/pr_review_contract.md`
- read `docs/codex/governance_policy.md`

When editing `activegraph_repo_manager/fixtures/**`:
- read `docs/codex/fixture_contract.md`

When editing `tests/**`:
- read `docs/codex/acceptance_criteria.md`
- read the relevant contract doc for the behavior under test

## Hard invariants

- Externally sourced objects must have stable `external_key` values.
- Ingest must use `find_by(external_key) -> patch-or-create`.
- Never blind-create GitHub-sourced objects.
- Behaviors must be deterministic.
- No direct network I/O in behavior bodies.
- No direct GitHub clients in behavior bodies.
- No direct subprocess calls in behavior bodies.
- No `datetime.now`, `date.today`, `random`, or `uuid.uuid4` in behavior bodies.
- GitHub, git, filesystem, and test execution go through tools.
- LLM judgment goes through LLM behaviors.
- LLM outputs must validate against strict Pydantic schemas and enums.
- Internal classifications and internal review findings may auto-apply.
- Planning mutations, GitHub writes, and file writes require approval-gated proposal objects.
- Treat `v1.1-plan.md` as planning/backlog input, not necessarily as a canonical roadmap.
- Prefer `PlanningItem` and `PlanningPatchProposal` over `RoadmapItem` and `RoadmapPatchProposal`.
