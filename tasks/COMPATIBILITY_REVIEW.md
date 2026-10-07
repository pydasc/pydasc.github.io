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

1. **Make document validation readable in separate stages — completed.**
   The validator now delegates to named inventory, tree, metadata provenance,
   checksum, Markdown provenance and link checks. The
   [follow-up verification](#document-validator-refactor) records the independent
   formatting checkpoint, validation-order coverage and complete output comparison.
2. **Extract shared test fixtures and group publication tests — completed.**
   `tests/publication_support.py` now owns the shared helpers. Publication
   contracts, Markdown links and output boundaries have separate test modules;
   source-lock and portal tests live with their existing related tests. See the
   [test-organization follow-up](#shared-publication-test-support) for retained
   coverage and independent collection checks.
3. **Share the release-check implementation across CI workflows — completed.**
   All three workflows call `scripts/check_release.py` for collection,
   deterministic comparison, validation, strict build and artifact scanning.
   Event conditions, environment approvals, tokens, permissions and deployment
   remain in the workflows. See the [follow-up verification](#shared-release-checks)
   for real release fixtures and retained pull-request secret-isolation tests.
4. **Define small shared publication-policy modules.**
   `validate_docs.py` and `update_source_locks.py` import private helpers from
   the collector. Once the validation stages are explicit, extract the bounded
   file/JSON readers and manifest/provenance types into a narrow shared API.
   Preserve symlink, file-identity, byte-limit and duplicate-key protections;
   keep this separate from behavioral changes to Markdown handling.

Item 4 remains a follow-up recommendation. The completed refactors preserve
the publication allowlist, source locks and approval requirements.

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

## Document-validator refactor

Follow-up to the first recommendation, starting from website commit `db2d0e1`.
The work was performed in two separate local stages:

1. Format the existing validator and expand its imports without extracting any
   checks. The syntax tree matches the original after normalizing grouped
   imports. Existing publication and input-safety tests pass at this checkpoint:
   **236 passed, 9 filesystem-specific skips**.
2. Extract `_load_inventory`, `_validate_tree`, `_validate_provenance`,
   `_read_checked_document`, `_validate_markdown_provenance` and `_validate_links`.
   The public `validate` function still reads the manifest first, checks the
   inventory and entire output tree, then completes each file's provenance,
   checksum, decoding, banner and links in inventory order. Inlining the helper
   bodies produces an AST identical to the original validation function.

Ten new regression cases pass against both the saved original and refactored
validator. They assert the same exception type and exact message for competing
inventory/tree, provenance/checksum, checksum/decoding and banner/link defects,
including reversed inventory order and the controlled CLI error result.
Existing adversarial tests remain intact.

Final verification: **287 passed, 9 case-insensitive-filesystem skips**. The
collector, document and physics validators, strict MkDocs build, site links,
accessibility and artifact scan pass. Both generated namespaces, the complete
inventory and **all 84 built-site files** are byte-identical to the baseline;
directory inventories also match. Formatting and whitespace checks pass.
The public CLI, error messages, safety rules, source locks, dependencies and
publication allowlist are unchanged. No upstream code was executed or modified.

## Shared publication test support

Follow-up to the second recommendation, starting from website commit `f3a8235`.
The four shared `git`, `repo`, `fixture` and `hashes` helpers now live in
`tests/publication_support.py`, formatted as ordinary multiline functions with
purpose docstrings. They still create temporary repositories, make actual Git
commits, write publication contracts and hash real files.

The former `tests/test_docs.py` is split by concern:

| Module | Collected cases | Scope |
| --- | --- | --- |
| `test_publication_contracts.py` | 51 | Approval, identity, source integrity, manifests and inventory metadata |
| `test_markdown_links.py` | 90 | Links, images, Markdown rendering and HTML policy |
| `test_output_boundary.py` | 41 | Determinism, containment, symlinks, file identities and atomic inventory writes |

Its three source-lock tests moved into `test_source_locks.py` and its portal
navigation test into `test_presentation.py`. Other helper consumers import
`publication_support` explicitly. `tests` is now a package, and `conftest.py`
centralizes the script import path; test modules no longer depend on another
test module being imported first. The README documents the organization.

Verification preserves all **296 collected cases and parameter IDs**, with only
their module paths changing. All **142 test/helper function ASTs** match the
baseline after normalizing equivalent import aliases and helper docstrings;
assertions, parameter decorators and existing fault-injection tests are intact.
No filesystem/Git behavior was replaced by mocks. All nine test modules collect
independently in fresh processes using pytest's importlib mode.

The full suite passes **287 tests**, with the same **9 case-insensitive-filesystem
skips**, now in `test_output_boundary.py`. Collection, repeated deterministic
assembly, document/physics validation, strict build, links, accessibility and
artifact checks pass. Generated documents, inventory and all 84 built-site files
are byte-identical to the baseline. Formatting, undefined/unused-import and
whitespace checks pass. Production scripts, dependencies, source locks and
publication policy are unchanged.

## Shared release checks

Follow-up completed on 7 October 2026 against baseline `cfbf132`.

`scripts/check_release.py` now owns the data-only release sequence used by
`docs-check.yml`, `deploy-pages.yml` and `update-source-locks.yml`: collect,
validate documents and physics references, collect again, compare the complete
generated tree and inventory, revalidate documents, build strictly, validate
site links and accessibility, and scan the artifact. Directory fingerprints
include empty directories. The updater now also revalidates after its second
collection, matching the other release workflows.

The artifact scanner retains the credential, private/local URL and path
patterns and the 5 MiB limit. It additionally fails on special files and
unreadable subtrees, scans binary bytes, and reports filenames without echoing
matching content. Bounded regular-file reads reuse the existing collector
protections. Site output cannot be a symlink or overlap an input checkout.
No publication allowlist, source lock or approval requirement changed.

The command accepts already-fetched local sources. Repository tests, event
conditions, environment approvals, token creation, permissions, source fetching,
PR creation, artifact upload and deployment remain in the workflows. A parsed
comparison against the baseline confirms all workflow and job controls and
retained steps are identical; all shell blocks pass `bash -n`. Workflow tests
require the exact same mandatory command in all three pipelines, enforce its
position before publishing, and retain PR/private-source secret isolation.

New tests build a real MkDocs site from temporary Git repositories, preserve
source bytes, and exercise failures in collection, deterministic comparison,
physics references, strict builds, site links, accessibility and artifact scans.
They include changed inventory bytes, empty directories, binary credentials,
symlinks, FIFOs, oversized files and inaccessible trees.

Verification: **318 passed, 9 skipped**; all skips still require a
case-insensitive filesystem. The shared release command passes against the
exact approved local checkouts. Generated documents, inventory and all **84
built-site files**, including directory inventories, match the baseline.
Formatting, undefined/unused-import and whitespace checks pass. Remote Actions
have not been run for these uncommitted changes.
