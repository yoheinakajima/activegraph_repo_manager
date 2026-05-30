# ActiveGraph repo manager

`activegraph_repo_manager` is a maintainer-facing repo-governance pack for the
ActiveGraph repository. The current implementation is a helper-level system: it
uses deterministic helpers, fixtures, and injected fake/read clients to mirror
repository state, replay classifications, link work to planning context, and
produce structured proposals without taking public external action.

It is read-only by default. Proposal objects are approval-gated, and external
actions are dry-run-only. This is not full runtime ActiveGraph orchestration;
the current code does not provide a background loop, dashboard, digest delivery,
automatic `PlanningItem` mutation, live GitHub write execution, or required live
LLM calls.

## Current capabilities

The current helper-level implementation covers these safe, auditable workflows:

- **Idempotent ingest** for externally sourced repository, issue, pull request,
  diff, and check-run objects. GitHub-derived records use stable
  `external_key` values and patch-or-create semantics.
- **Repo grasp** over deterministic repository snapshots, including file,
  symbol, and test-surface summaries.
- **Issue and PR classification replay** from recorded fixture outputs rather
  than live LLM calls.
- **Deterministic linking** between issues, pull requests, and planning items.
- **Contract guard and structured PR review replay** using strict recorded
  outputs and schema-shaped findings.
- **`PlanningPatchProposal` generation** for planning follow-up suggestions.
  These are proposal objects; planning mutations are not automatic.
- **`ExternalActionProposal` generation and dry-run external actions** for
  review/planning follow-ups. Dry-run execution returns structured results and
  keeps `no_external_write` true.
- **Live-write boundary stubs** that deliberately return disabled or
  not-implemented outcomes instead of performing writes.
- **GitHub read-only sync** through an injected read client or fake client.
  Tests remain fixture/fake-client based and do not require credentials.
- **Keyless demo integration** that exercises the safe helper-level path without
  GitHub credentials or live LLM calls.
- **Pack integration audit** checks for import hygiene, settings defaults,
  prompt/fixture consistency, and safety boundaries.

## Explicit non-capabilities and safety boundaries

The repo-governance pack intentionally does **not** currently do the following:

- perform live GitHub writes;
- post comments, labels, reviews, issues, or pull requests to GitHub;
- require live LLM calls for the existing replay/demo/test paths;
- execute runtime file writes from repo-manager behavior;
- run background maintainer loops;
- provide dashboard or digest behavior as a verified runtime feature;
- automatically mutate `PlanningItem` records;
- execute runtime ActiveGraph approval flows end-to-end.

Write-like outcomes must remain represented as proposal objects until a future
live-write PR adds explicit implementation, approval checks, denied/rejected
execution tests, and operator-controlled settings.

## Keyless demo

Run the keyless demo tests with:

```bash
pytest tests/test_keyless_demo.py
```

The keyless demo uses offline fixtures by default. It verifies deterministic
replay of ingest, repo grasp, issue/PR classification, linking, contract guard,
structured PR review findings, and planning proposal generation. The default
path does not contact GitHub, does not read credentials, and reports zero live
LLM calls.

The demo can include GitHub read-only sync only when a read client is injected.
If no injected client is provided, requesting that mode raises an error instead
of falling back to implicit credentials or network behavior.

## GitHub read-only sync with injected clients

Run the GitHub read-only sync tests with:

```bash
pytest tests/test_github_readonly_sync.py
pytest tests/test_github_readonly_orchestrator.py
```

The read-only sync boundary is based on an injected client protocol. The helper
functions call read methods such as repository, issue, pull request, file, and
check retrieval on the supplied client, normalize those payloads into stable
external keys, and ingest them through the same idempotent helpers used by the
fixture path.

The test suite uses fake clients. Those fakes expose read methods and fail if a
write method is invoked. Sync summaries include read-side counts and keep write
counters at zero. There is no default live GitHub client and no required token or
credential read in the tested path.

## ExternalActionProposal dry-run behavior

Run the external action policy tests with:

```bash
pytest tests/test_external_action_policy.py
```

`ExternalActionProposal` helpers can derive proposed GitHub/comment/review or
follow-up PR actions from structured review findings and planning proposals.
They remain proposals until approved. Dry-run execution is deterministic and
side-effect free: approved proposals can return a `dry_run_applied` result with a
payload summary, evidence references, and `no_external_write` set to true.

If approval is required and the proposal is still only proposed, dry-run
execution reports that the proposal is not approved and performs no external
write. If dry-run mode is disabled and write gates are otherwise evaluated, the
current live-write boundary still returns a not-implemented result rather than
performing a public write.

## Why live writes remain disabled

Live writes are disabled or unimplemented by design. The settings defaults keep
external writes, GitHub write tools, and file write tools off while keeping
dry-run external actions on. The live-write boundary exists to prove that write
attempts remain blocked, disabled, or not implemented in this helper-level
phase.

Before any live-write PR, maintainers must add all of the following in a focused
future change:

1. explicit live-write tools and operator-controlled settings;
2. approval enforcement for every public write path;
3. tests proving rejected, denied, unapproved, and disabled actions cannot
   execute;
4. tests proving dry-run mode still performs no write;
5. deterministic audit output for any approved execution path;
6. documentation that distinguishes proposed, approved, dry-run, and executed
   states;
7. a separate review of credential handling and network boundaries.

## Pack integration audit

Run the pack integration audit with:

```bash
pytest tests/test_pack_integration_audit.py
```

The audit verifies that package imports are clean, behavior/tool modules follow
pack conventions, behavior bodies avoid forbidden I/O and nondeterminism tokens,
prompts and fixtures remain versioned and secret-free, and settings defaults
preserve the read-only/dry-run safety posture.

## Full current verification suite

Run the current verification suite with the same commands used for this phase:

```bash
pytest tests/test_pack_loads.py
pytest tests/test_no_global_registration.py
pytest tests/test_no_io_in_behaviors.py
pytest tests/test_ingest_idempotency.py
pytest tests/test_repo_grasp.py
pytest tests/test_issue_classification_replay.py
pytest tests/test_pr_review_replay.py
pytest tests/test_planning_proposal_policy.py
pytest tests/test_keyless_demo.py
pytest tests/test_external_action_policy.py
pytest tests/test_live_write_boundary.py
pytest tests/test_github_readonly_sync.py
pytest tests/test_github_readonly_orchestrator.py
pytest tests/test_pack_integration_audit.py
pytest tests/test_repo_manager_docs.py
```

These commands use the existing pytest suite. They do not require network access,
GitHub credentials, live LLM credentials, or live external writes.
