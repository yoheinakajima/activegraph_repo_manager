# Repo manager current status and next gates

This document summarizes the current state of `activegraph_repo_manager`, a
helper-level repo-governance pack for the ActiveGraph repository. It is intended
for maintainers who need a concise view of what exists today, what is still only
fixture or fake-client based, and what gates must pass before any live runtime
reads or live writes are claimed.

## Current helper-level capabilities

The current implementation provides deterministic helper-level workflows for:

- idempotent ingest of repository, issue, pull request, diff, and check-run
  records using stable `external_key` values;
- repository grasp over deterministic snapshots of files, symbols, and tests;
- issue and pull request classification replay from recorded outputs;
- deterministic linking between issues, pull requests, and planning context;
- contract-guard and structured pull-request review replay through strict
  schemas and enums;
- `PlanningPatchProposal` and `ExternalActionProposal` object generation;
- GitHub read-only sync helpers that require an injected read client and are
  tested with fake clients;
- dry-run-only external action execution that reports structured results without
  public side effects;
- live-write boundary stubs that return disabled or not-implemented outcomes
  instead of performing writes.

These capabilities are helper-level building blocks. They are not a background
service, dashboard, digest runner, autonomous maintainer, or end-to-end runtime
ActiveGraph approval executor.

## Fixture and fake-client based behavior

The safe paths are intentionally fixture and fake-client based:

- keyless demo coverage uses offline fixtures and recorded replay outputs;
- GitHub read-only sync tests use injected fake clients rather than implicit
  credentials or a default live GitHub client;
- fake clients expose read methods and are expected to fail if write methods are
  invoked;
- existing classification and review paths do not require live LLM calls;
- tests do not require network access, GitHub credentials, or live LLM
  credentials.

## Read-only boundaries

The current repo-governance pack is read-only by default. GitHub-derived records
are mirrored into local graph-shaped objects through deterministic helpers.
Public side effects remain outside the implemented runtime boundary.

Read-side behavior must continue to preserve these constraints:

- no implicit credential reads;
- no direct GitHub clients inside behavior bodies;
- no direct network I/O inside behavior bodies;
- no blind-create ingest for externally sourced objects;
- GitHub-sourced objects continue to use stable `external_key` values and
  patch-or-create semantics.

## Dry-run-only external action behavior

External actions currently remain dry-run-only. Approved proposal objects may be
summarized as dry-run results, but the dry-run path must keep
`no_external_write` true and must not post comments, labels, reviews, issues,
pull requests, files, or any other public effects.

Dry-run behavior is useful for proving payload shape, audit output, and approval
state handling before any live executor exists. It is not evidence that live
writes are implemented.

## Disabled or unimplemented live capabilities

Live writes are disabled or unimplemented by design. The repo manager does not
yet provide:

- live GitHub writes;
- live LLM execution as a required path;
- runtime ActiveGraph approval execution;
- automatic `PlanningItem` mutation;
- dashboard or digest runtime behavior;
- background service orchestration;
- runtime file writes from repo-manager behavior;
- broadened helper functionality beyond the documented helper-level paths.

## Tests proving the current safety boundary

The current safety boundary is covered by targeted pytest checks:

- `pytest tests/test_keyless_demo.py` proves the keyless helper path runs from
  offline fixtures without credentials or required live LLM calls.
- `pytest tests/test_github_readonly_sync.py` proves read-only sync behavior
  works through injected fake clients and keeps write counts at zero.
- `pytest tests/test_github_readonly_orchestrator.py` proves orchestration of
  the read-only sync path remains fake-client/injected-client based.
- `pytest tests/test_external_action_policy.py` proves external actions are
  proposal and dry-run oriented, with approval-state handling and no external
  write effects.
- `pytest tests/test_live_write_boundary.py` proves live write attempts remain
  blocked, disabled, or not implemented.
- `pytest tests/test_pack_integration_audit.py` audits import hygiene, settings
  defaults, prompt and fixture consistency, and safety boundary conventions.


## Local command surface status

Implemented for keyless/demo use:

- SQLite-backed local state in `activegraph_repo_manager.state`.
- Deterministic local-state questions in `activegraph_repo_manager.query`.
- Offline CLI entry point via `python -m activegraph_repo_manager`.
- `keyless-demo`/`demo`, `ask`, `status`, and `snapshot` commands.

Current boundaries remain unchanged: the command surface does not create live
GitHub clients, does not perform live LLM calls, and does not execute external
writes.

## Safe to run today

The following existing pytest commands are safe to run today and do not require
network access, GitHub credentials, live LLM credentials, or live writes:

```bash
pytest tests/test_keyless_demo.py
pytest tests/test_github_readonly_sync.py
pytest tests/test_github_readonly_orchestrator.py
pytest tests/test_external_action_policy.py
pytest tests/test_live_write_boundary.py
pytest tests/test_pack_integration_audit.py
```

## Before live read runtime wiring

Before claiming live read runtime wiring, a future PR should add or confirm:

1. explicit operator settings for any live read mode;
2. injected live read client construction outside behavior bodies;
3. credential handling that is opt-in, documented, and not used by default;
4. tests that keep fixture and fake-client paths credential-free;
5. tests for missing, malformed, and denied read configuration;
6. audit summaries that distinguish fixture reads, fake-client reads, and live
   reads;
7. documentation that live read mode is read-only and cannot escalate into
   writes.

## Before-live-write gates

Before live write execution can be claimed, a separate focused PR must pass
before-live-write gates including:

1. explicit live-write tools and operator-controlled settings;
2. approval enforcement for every public write path;
3. tests proving rejected, denied, unapproved, disabled, and malformed actions
   cannot execute;
4. tests proving dry-run-only mode still performs no external write;
5. deterministic audit output for proposed, approved, dry-run, and executed
   states;
6. credential and network-boundary review;
7. implementation that keeps behavior bodies free of direct network I/O,
   direct GitHub clients, direct subprocess calls, runtime file writes, and
   nondeterministic calls;
8. documentation updates that clearly separate helper-level proposals from live
   execution.

## Do not claim yet

Do not claim that the repo manager currently provides:

- live GitHub writes;
- live LLM execution as a required path;
- runtime ActiveGraph approval execution;
- automatic `PlanningItem` mutation;
- dashboard or digest runtime behavior;
- background service orchestration.

## Recommended next PRs

Recommended follow-up PRs, in order:

1. live read runtime wiring with explicit settings and injected clients, while
   preserving fake-client tests and read-only defaults;
2. stronger audit documentation for distinguishing fixture, fake-client, and
   future live-read runs;
3. focused approval-runtime design notes for how proposal objects would be
   approved and executed without adding writes yet;
4. separate live-write implementation only after the before-live-write gates are
   agreed, implemented, and tested.
