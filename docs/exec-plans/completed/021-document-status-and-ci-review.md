# Reconcile documentation, tasks and CI status

4 October 2026. Complete the docs/ and tasks/ status review. Acceptance:
inventory current/historical/generated documents, update supported completion
status, preserve the publication boundary, and verify local/remote checks.

## Changes and evidence

Update current portal descriptions to distinguish approved historical source
snapshots from newer upstream implementation and private scientific evidence.
Reconcile task and deployment checklists with observed successful runs. Record
completed Tasks 001–019 and dependency maintenance 020, while retaining source
promotion, release-specific review and unverified governance items as pending.
Add an internal status index and per-file inventory. Historical logs remain
unchanged. Three ignored legacy prompt files receive historical-status notices
and remain ignored; generated imports are rebuilt only through the collector.
No source lock, manifest, workflow, dependency or code is changed.

See [the status index](../../operations/document-status.md) for exact workflow
URLs, tested commits, source checkout/content commits and deployed artifact SHA.
The inventory at ../../operations/document_status_inventory_20261004.json
records the reviewed paths.

## Verification

- Isolated pinned environment: pip check passes.
- Full pytest: **276 passed, 1 skipped**, 128.33 s. The skip at
  tests/test_docs.py:593 requires a case-sensitive filesystem; this Mac's
  filesystem is case-insensitive.
- Both exact locked source checkouts collect successfully; two collections
  produce byte-identical staged files and generated inventory.
- Document/physics validators, strict MkDocs build, site links/accessibility and
  full artifact scan pass. Internal operations/status files remain unpublished.
- Material's MkDocs 2 banner is informational; the pinned strict build passes.
- Final whitespace and inventory hash checks pass.

## Remote checks and remaining work

Latest Documentation checks and Pages deployment at 95de4c6 pass, including
source-docs access. The latest observed scheduled source-update proposal also
passes at its older revision; no new proposal was dispatched. pydasc CI passes
at 74fabb7. The user pushed dasc 4b49c5f during this review; repository and
scientific jobs both passed in run 37209940722, as did the local tests.

No new credential/environment approval, commit, push or deployment was made.
This edit needs its own future CI. Current upstream research documents require
an explicit source-contract/lock review before public promotion. A successful
build does not complete physical validation or human governance decisions.
