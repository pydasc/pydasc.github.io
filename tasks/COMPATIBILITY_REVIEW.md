# Upstream compatibility and repository review

This internal review follows the CPU/GPU publication proposal. It is outside
`docs/` and is not published.

## Checked revisions and scope

| Input | Revision | Result |
| --- | --- | --- |
| Website baseline | `b2d46a8` | Existing publication locks and generated release remain compatible |
| PyDASC current checkout | `56ae3883e2a4a80a3f0dfcdaf5361d59e8891952` | Current files differ from the historical publication offer; not eligible for a lock-only update |
| DASC current checkout | `784de43472bcf82b071fe395bef65c1b6cf7924b` | Publication decision remains blocked, with no approved files |

The website consumes Markdown and Git objects, not upstream Python APIs. This
review exercised source-contract compatibility and the complete website build;
it did not install or execute upstream packages or run scientific CPU/GPU
calculations. Both source worktrees were clean when inspected and were left
unchanged. Tests and collection used independent temporary clones.

PyDASC still offers `b5676d387d027958e804af6bebff4862dd4967c1`; its current
README has different bytes and its old public workflow path is missing. DASC
still names `0960f639055c4fe60029175ad603d1f52dc2fc53` with a blocked decision.
The newer implementation/refactor commits do not update either publication
contract. The [publication proposal](CPU_GPU_PUBLICATION_REVIEW.md) therefore
remains open; production locks and the allowlist are unchanged.

## Findings fixed

### Source updater accepted a candidate that collection could not use

`scripts/update_source_locks.py` checked contract metadata, then wrote the new
lock without inspecting the selected source bytes and links. Reproduced using
current PyDASC with the existing approved DASC checkout: the updater accepted
the candidate, but collection immediately failed with
`source differs from approved commit: README.md`.

The updater now calls the existing collector into temporary output before
writing the manifest. This reuses the publication checks for regular files,
approved bytes, links, images, HTML and source immutability. No source package
is imported or executed. Five regression cases cover changed/missing files,
symlinks, approved content with a broken link, and a content failure with
`--skip-unapproved`. Rejected candidates leave the manifest unchanged.

Retesting the real current PyDASC candidate now fails before writing the lock.
Testing both current upstream checkouts rejects DASC's blocked decision as
expected. Existing workflow validation after the updater remains in place.

### Accessibility audit counted table headers across the whole page

`scripts/validate_accessibility.py` accepted multiple tables whenever any one
of them had a header. It now tracks headers per table, using a stack so a nested
table's header cannot satisfy its parent. Regression coverage checks both
sibling orders, nested tables, and a valid page containing two headed tables.

### Local preview instructions skipped required source collection

README previously described a scaffold-only strict build and ran `mkdocs serve`
before collection, even though the configured navigation requires the imported
pages. It now explains isolated local clones at the manifest locks and runs
collection and validation before build/serve. It also documents the updater's
new validation and the per-table accessibility check.

## Refactor opportunities, in priority order

1. **Make document validation readable in separate stages.**
   `scripts/validate_docs.py:25` combines inventory schema, directory traversal,
   provenance, checksums and Markdown links in one function, with several
   single-line conditionals. Split it into named inventory, tree, provenance
   and link checks without changing validation order, error behavior or safety
   rules. First format the code independently; retain adversarial coverage and
   compare the complete generated output before and after.
2. **Extract shared test fixtures and group publication tests.**
   `tests/test_docs.py:17` contains compact Git/repository helpers that other
   test modules import from the test module itself. Move those helpers to a
   dedicated test-support module and split contract, link and output-boundary
   tests by concern. Keep temporary Git repositories and real filesystem tests;
   avoid replacing them with mocks that bypass the behavior under test.
3. **Share the release-check implementation across CI workflows.**
   `docs-check.yml`, `deploy-pages.yml` and `update-source-locks.yml` repeat
   collection, deterministic comparison, validation and artifact scanning.
   Extract repository-owned commands for these data-only checks so one pipeline
   cannot miss a future gate. Keep event conditions, environment approvals,
   token creation, workflow permissions and deployment in the workflows, and
   retain tests proving pull-request jobs cannot access private-source secrets.
4. **Define small shared publication-policy modules.**
   `validate_docs.py` and `update_source_locks.py` import private helpers from
   the collector. Once the validation stages are explicit, extract the bounded
   file/JSON readers and manifest/provenance types into a narrow shared API.
   Preserve symlink, file-identity, byte-limit and duplicate-key protections;
   keep this separate from behavioral changes to Markdown handling.

These are follow-up recommendations, not completed refactors. The current
changes fix the demonstrated gaps without restructuring the publication system.

## Verification

- Full pytest: **277 passed, 9 skipped**. The skips require a case-insensitive
  filesystem; this Linux filesystem is case-sensitive. Tests ran outside the
  sandbox to permit temporary Unix-socket fixtures.
- `pip check`: no broken requirements.
- Collection at the existing production locks and a second byte-for-byte
  assembly comparison: passed.
- Document and physics validators, strict MkDocs build, site-link validation
  and the revised accessibility audit: passed.
- Complete artifact scan for symlinks, oversized files and forbidden
  credential/private-path patterns: passed.
- Whitespace review: passed. The final Git diff contains the intended fixes,
  tests and maintenance documentation; no generated output or upstream changes.

No source promotion, commit, push, workflow dispatch or deployment was performed.
