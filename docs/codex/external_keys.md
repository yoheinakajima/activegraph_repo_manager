# External keys and idempotent ingest

Every externally sourced object must have a stable `external_key`.
Ingest rule: `find_by(external_key) -> patch existing OR create new`.
Never blind-create GitHub-sourced objects.
