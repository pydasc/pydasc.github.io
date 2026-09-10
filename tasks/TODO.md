# Repository TODO

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
- [ ] After an authorized commit and push, confirm that both Documentation
  checks and Deploy documentation to Pages succeed.

## P2 — Strengthen maintainability

- [x] Add explicit tests rejecting duplicate source and destination entries in upstream
  publication contracts, not only duplicate website destinations.
- [x] Validate publication-decision evidence, DASC attribution, inventory
  provenance fields, and generated Markdown provenance banners.
- [x] Reject active raw HTML, alternate reference-style links, and unsafe URL
  schemes while preserving DASC attribution in generated release records.
- [x] Replace regex-only raw HTML checks with multiline-aware element and
  attribute parsing, including style and alternate resource attributes.
- [ ] Refactor the compact formatting in `scripts/validate_docs.py` and
  `tests/test_docs.py` without changing behavior, then adopt a consistent lint
  configuration if desired.
- [ ] Keep `requirements-docs.txt` pinned and evaluate the announced MkDocs 2.0
  compatibility break before any dependency upgrade.

## P3 — Recurring release maintenance

- [ ] Review automated source-lock pull requests as public content releases;
  verify licenses, publication decisions, immutable commits, and every newly
  selected file.
- [ ] Periodically retest narrow-screen table scrolling, keyboard focus,
  forced-colors/high-contrast presentation, equation copying, and print output.
- [ ] Keep internal task, browser-control, execution-plan, and development-note
  files excluded from the published site.
