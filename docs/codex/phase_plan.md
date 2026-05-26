# Phase plan

Phase 0: read-only mirror and idempotent ingest.
Phase 1: repo grasp (files/symbols/tests).
Phase 2: issue/PR classification and linking.
Phase 3: PR review and contract guard.
Phase 4: gated planning proposals.
Phase 5: approved external actions.

Phase 5b scaffold note:
- Introduces the live-write boundary and settings gates only.
- Real external writes remain unimplemented.
- Future live-write implementation must require approval, explicit settings, denied/rejected-action tests, and a separate PR.


Phase 5c read-only sync note:
- GitHub read-only sync may ship before any live-write implementation.
- Live read operation must use explicit settings and/or injected clients.
- Tests must remain fixture/fake-client based (no required credentials).
- Write actions remain disabled until a separate live-write PR.
