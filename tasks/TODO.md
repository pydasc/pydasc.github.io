# Repository TODO

**Current task entry point — 8 October 2026.**
[Local refactoring results](../docs/operations/refactoring-progress.md) are separate
from the [historical 4 October remote CI record](../docs/operations/document-status.md).
No new remote success or deployment is inferred from local commits.
Recurring maintenance and unverified governance remain open.

This file tracks repository work that is not intended for publication. Complete
items in priority order; do not weaken the publication boundary to bypass a
failing check.

## P0 — Reviewed publication-security changes

- [x] Review the committed `scripts/collect_docs.py` changes that load each upstream
  publication contract from its immutable locked commit and reject a differing
  worktree copy.
- [x] Confirm that SVG remains excluded from imported publication formats until
  a strict, reviewed sanitizer and adversarial test suite exist.
- [x] Review the committed `scripts/validate_docs.py` changes that compare generated
  inventory destinations and provenance with `docs-manifest.yml`.
- [x] Review the new regression tests for dirty contracts, active SVG content,
  duplicate website destinations, and manifest/inventory disagreement.

## P1 — Complete release verification

- [ ] Promote the CPU parallel/GPU documentation after the upstream publication
  contracts approve the reviewed content. See the
  [7 October release proposal](CPU_GPU_PUBLICATION_REVIEW.md) for exact source
  revisions, proposed public files and the workflow-guide migration blocker.

- [x] Run the complete exact-checkout acceptance sequence:

  ```bash
  python -m pytest
  python scripts/collect_docs.py --manifest docs-manifest.yml --output docs \
    --pydasc .source-checkouts/pydasc --dasc .source-checkouts/dasc
  python scripts/validate_docs.py --manifest docs-manifest.yml --docs docs
  python scripts/validate_physics_docs.py --docs docs
  mkdocs build --strict
  python scripts/validate_site.py --site site \
    --css docs/stylesheets/readthedocs.css
  python scripts/validate_accessibility.py --site site
  git diff --check
  ```

- [x] Verify deterministic assembly by snapshotting `docs/pydasc/`,
  `docs/dasc/`, and `docs/generated-inventory.json`, collecting again, and
  confirming no difference.
- [x] Inspect the final diff and ensure it contains only approved repository
  changes. Do not include `site/`, caches, temporary checkouts, credentials, or
  local browser guidance.
- [x] Confirm Documentation checks and Deploy documentation to Pages succeed
  at committed 95de4c6 (4 October 2026; run links in the status record).
- [ ] Recheck both workflows after the next authorized commit/push; local
  documentation edits are not covered by the previous remote success.

## P2 — Strengthen maintainability

- [x] Integrate the remote [compatibility review](COMPATIBILITY_REVIEW.md), including
  candidate collection before lock writes, validator ordering regressions and
  real release integration tests, with the local WEB-REF module/workflow layout.
- [ ] Verify the reconciled merge on remote CI after a separately authorized push;
  the older remote success records do not cover this merged result.

- [x] Add explicit tests rejecting duplicate source and destination entries in upstream
  publication contracts, not only duplicate website destinations.
- [x] Validate publication-decision evidence, DASC attribution, inventory
  provenance fields, and generated Markdown provenance banners.
- [x] Reject active raw HTML, alternate reference-style links, and unsafe URL
  schemes while preserving DASC attribution in generated release records.
- [x] Replace regex-only raw HTML checks with multiline-aware element and
  attribute parsing, including style and alternate resource attributes.
- [x] Refactor compact Python formatting and validator/test responsibilities;
  pin and check Ruff formatting (WEB-REF-08 through WEB-REF-13).
- [x] Refresh the pinned documentation dependency baseline and validate it
  with strict MkDocs 1.6.1 checks (record 020).
- [ ] Evaluate MkDocs 2.0 compatibility before a future major upgrade.

## P3 — Recurring release maintenance

- [ ] Review automated source-lock pull requests as public content releases;
  verify licenses, publication decisions, immutable commits, and every newly
  selected file.
- [ ] Periodically retest narrow-screen table scrolling, keyboard focus,
  forced-colors/high-contrast presentation, equation copying, and print output.
- [ ] Keep internal task, browser-control, execution-plan, and development-note
  files excluded from the published site.
