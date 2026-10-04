# Refresh website CI dependency baseline

4 October 2026. Acceptance: isolated installation, repository tests, deterministic
reviewed-source assembly, strict MkDocs build, links/accessibility and artifact
scan. Keep existing publication locks, access protections and deployment scope.

Refresh all existing requirements-docs.txt pins from the upgraded environment,
including Material 9.7.7, PyYAML 6.0.3, pytest 9.1.1 and pymdown-extensions 12.1.
All three workflows now use Python 3.13.16 and run pip check after installation.
A temporary clean environment installs all 32 pinned packages successfully.
The old local .venv points at a removed Homebrew Python; README documents
recreation rather than silently changing that environment.

## Local validation

- pip check: pass.
- pytest: 276 passed, 1 expected case-sensitive-filesystem skip (146.73 s).
- Initial sandbox-only run could not create Unix sockets; rerun with local
  socket permission passed both tests without changing or skipping them.
- Reviewed source contract and physics-document validation: pass.
- Deterministic assembly: byte-identical generated sources/inventory.
- MkDocs strict build, site links, accessibility and full artifact scan: pass.
- Material emits an upstream informational banner about MkDocs 2; the pinned
  MkDocs 1.6.1 strict build succeeds. No migration was performed.
- Source-lock updater and Pages deployment side effects were not executed.

## Remote status and limits

Read-only GitHub inspection before changes: the latest pydasc CI and website
check/deploy workflows were successful; dasc had no workflows/runs. These edits
have not been committed, pushed or run on GitHub. Local validation is on macOS,
not an Ubuntu runner. All five resulting workflows pass actionlint 1.7.12
(checksummed official binary; optional ShellCheck/Pyflakes integrations disabled).
No publication locks, approved source contents, scientific conventions or solver
algorithms were changed. No skipped check is counted as hardware/data validation.
