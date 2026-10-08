# DASC Documentation Website

This repository builds the public documentation portal for DASC and PyDASC with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). It provides a single Read-the-Docs-like interface while the project documentation remains authored in its respective source repository.

- Website repository: `https://github.com/pydasc/pydasc.github.io`
- Published website: `https://pydasc.github.io/`
- PyDASC source: `https://github.com/pydasc/pydasc`
- DASC source: `https://github.com/pydasc/dasc`

## Design

The portal contains hand-written landing and project-selection pages plus a reviewed subset of public documentation imported from `pydasc` and `dasc`. The build has four stages:

1. Read `docs-manifest.yml`, the sole allowlist of publishable upstream files.
2. Fetch the exact reviewed commit of each source repository into temporary storage.
3. Copy and, where necessary, safely rewrite the selected documents into `docs/pydasc/` and `docs/dasc/`.
4. Build the static site with MkDocs and deploy its `site/` artifact through GitHub Pages.

No upstream repository is mounted as a writable dependency, no upstream code is executed, and no unlisted file is published.

The hand-written DASC section is organized around the physics project rather
than its planned papers: project overview, shared foundations, DA/TPSA and Lie
methods, TGF and eigenmode formulations, method selection, reproducibility, and
research outputs. These architecture pages summarize scope without copying the
excluded upstream LaTeX derivations. The allowlisted upstream DASC README remains
available under Research outputs and publications with its source provenance and
status intact.

## Repository layout

```text
.
├── .github/workflows/docs-check.yml
├── .github/workflows/deploy-pages.yml
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   ├── pydasc/                 # generated from allowlisted PyDASC docs
│   ├── dasc/                   # generated from allowlisted DASC docs
│   ├── assets/
│   └── overrides/
├── scripts/collect_docs.py
├── scripts/validate_docs.py
├── tests/
├── docs-manifest.yml
├── mkdocs.yml
├── requirements-docs.txt
├── AGENTS.md
└── README.md
```

## Publication manifest

Only entries in `docs-manifest.yml` may cross the public-site boundary. Production
checkout commits are full commit SHAs so a build is reproducible and cannot
silently ingest newly pushed content. Each source also names the upstream
publication contract that approves the selected files.

```yaml
schema_version: 2
sources:
  pydasc:
    repository: https://github.com/pydasc/pydasc
    checkout_commit: "<40-character commit SHA>"
    publication_manifest: docs/publication-manifest.json
    files:
      - source: README.md
        destination: pydasc/index.md
  dasc:
    repository: https://github.com/pydasc/dasc
    checkout_commit: "<40-character commit SHA>"
    publication_manifest: docs/publication-manifest.json
    files:
      - source: README.md
        destination: dasc/index.md
```

Adding a manifest entry is a publication decision. Confirm that the file is intentionally public, properly licensed, free of secrets and private links, and suitable for the portal. Wildcards and directory-wide copying are intentionally unsupported.

The generated `docs/pydasc/` and `docs/dasc/` directories are intentionally ignored by Git and created in CI. Source acquisition fetches the exact locks separately. The collector validates the complete manifest and local approved checkouts, verifies path containment and file types, and then replaces only those two generated namespaces from a temporary staging tree. Repeated runs are covered by a byte-for-byte determinism test.

Before staging or replacing output, the collector checks that the output directory and source checkouts do not overlap, that no output namespace contains the input manifest, and that every existing output target has the expected type. Overlap and manifest checks compare filesystem identities along existing ancestors, including capitalization aliases on case-insensitive filesystems and destinations that do not yet exist. Output-root and namespace symlinks are rejected. The inventory must be absent or a regular file; symlinks, dangling symlinks, directories, and special files are rejected before either namespace is changed. Inventory updates use an atomic replacement from a temporary file in the output directory, and document validation also rejects inventory symlinks and special files. Keep source checkouts outside the output directory.

Manifest, inventory, and published-document reads use a shared bounded regular-file reader. It checks filesystem identity before reading and opens nonblocking without following the final symlink, preventing replacement pipes or symlinks from bypassing the initial check. Website-manifest symlinks are resolved explicitly; source contracts and generated files cannot be symlinks. These inputs are limited to 5 MiB each. Output validation rejects special files anywhere in the generated namespaces and fails on inaccessible subdirectories. Schema validation rejects duplicate keys, non-string mapping keys, invalid field types, and paths that normalize to an empty path, with controlled errors. Regression coverage for these boundaries lives in `tests/test_input_safety.py`.

Relative links to allowlisted files are relocated within the portal. Links to existing but unlisted upstream documents are rewritten to immutable GitHub URLs at the same commit; missing or unsafe targets fail collection. Images must be explicitly allowlisted, and arbitrary remote content is never downloaded.

Link discovery verifies individual source occurrences with the configured Markdown renderer; links inside comments and code examples are left untouched. HTML entities are decoded for validation, while unchanged URLs retain their original Markdown spelling and rewritten URLs encode syntax-sensitive characters. Imported rendered HTML is checked for active elements, unsafe attributes, and unsafe URL schemes. Duplicate HTML attributes are rejected during both publication and built-site validation.

## Configuration

[`mkdocs.yml`](mkdocs.yml) is the current configuration, including explicit
navigation, theme features, hooks and internal-document exclusions. Change that
file rather than copying an old scaffold. The build rejects documentation pages absent from explicit navigation, honoring
internal exclusions. New imports require a reviewed manifest
entry and matching upstream approval; authored pages require explicit navigation.

### Presentation

The portal uses a repository-owned, classic documentation theme adaptation in
`docs/stylesheets/readthedocs.css`. It retains Material for MkDocs behavior while
providing a fixed 300 px desktop navigation rail, bounded reading column,
breadcrumb trail, responsive drawer, print rules, and reduced-motion support.
The implementation uses local/system font fallbacks and does not download fonts,
styles, branding, advertising, analytics, or assets from Read the Docs or another
documentation project.

Previous/next controls are filtered by the repository-owned footer override so
they stay within the current portal, PyDASC, or DASC section. Cross-project
movement remains available through the explicit left navigation and project
chooser.

After building, validate subpath-safe links and presentation assets with:

```bash
python scripts/validate_site.py --site site \
  --css docs/stylesheets/readthedocs.css
```

## Local development and complete release checks

Use Python **3.13.16** from `.python-version` and Git. From this repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
python -m pip check
python scripts/check_dependencies.py
python -m ruff format --check scripts tests
python -m pytest -q -rs
```

These tests use synthetic sources and need no private credentials. For a complete
site, provide two local checkouts at the exact `docs-manifest.yml` commits:

```bash
python scripts/check_release.py \
  --pydasc /path/to/approved-pydasc --dasc /path/to/approved-dasc
```

This one command runs tests, collects approved inputs twice, compares their bytes,
validates provenance/physics, builds strictly, validates the rendered site and
accessibility, and scans the complete artifact. `--skip-tests` is only for reusing
a preceding successful test run of the same checkout. `--manifest`, `--config`,
`--docs`, and `--site` accept explicit paths; docs must match the configuration.
It neither acquires sources, changes locks, proposes a PR nor deploys.

Protected CI also requires browser checks. With Node **24.19.0** available:

```bash
npm ci --ignore-scripts --no-audit --no-fund
npx --no-install playwright install chromium
python scripts/check_release.py \
  --pydasc /path/to/approved-pydasc --dasc /path/to/approved-dasc --browser-tests
```

After collection, `python -m mkdocs serve` provides a local preview at
`http://127.0.0.1:8000/`. The explicit imported navigation requires the generated
files; this is not a source-free scaffold preview. Never hand-edit generated pages.
Read the [dependency procedure](docs/operations/dependency-maintenance.md) and
[browser/manual checklist](docs/operations/browser-checks.md) for environment and
accessibility details.

## API documentation and executable content

The current release is static. PyDASC's allowlisted `docs/PUBLIC_API.md` is an
authored public-interface policy page, not generated API output. Neither reviewed
source contract approves generated API documentation, notebooks, or executable
examples, so the website does not install either source package or provide a
notebook/API execution pipeline.

Links from approved pages to unlisted upstream notebooks or examples are rewritten
to immutable GitHub URLs at the reviewed commit. Those targets are not copied,
rendered, executed, or included in the publication inventory. See the internal
decision record in `docs/architecture/api-and-examples-decision.md` for the
requirements that a future, explicitly reviewed approval must satisfy.

## Updating imported documentation

1. Choose a reviewed commit from `pydasc/pydasc` or `pydasc/dasc`.
2. Audit each proposed source file for public suitability and licensing.
3. Update the source `checkout_commit`, `publication_manifest`, and explicit file
   entries in `docs-manifest.yml` as required by the reviewed source contract.
4. Run collection, validation, tests, and the strict MkDocs build.
5. Inspect the rendered navigation, links, images, code blocks, attribution, and mobile layout.
6. Submit the manifest change and any necessary portal changes for review.

Do not hand-edit generated copies. Fix content upstream or adjust the reviewed collection/transformation rules.

## Continuous integration and deployment

`docs-check.yml` runs for documentation-related pull requests and main-branch
pushes with `contents: read` permission. Its unprivileged `docs` job runs repository
tests and validates the website manifest without App secrets or private sources.
On main pushes only, the separate `source-docs` job waits for approval in the
protected `docs-sources` environment. It checks out the website without
persisting credentials, reads the exact source locks from `docs-manifest.yml`,
fetches those commits over authenticated HTTPS using a short-lived, read-only
GitHub App token into detached temporary worktrees, and
never executes source-repository configuration or code. It runs the same tests,
collector, validator, and strict MkDocs build used locally, repeats collection and
compares the complete generated tree byte-for-byte, and scans the built `site/`
artifact for symlinks, oversized files, credentials, and private or local paths.
Its dependency cache is keyed by `requirements-docs.txt`; it neither uploads nor
deploys an artifact.

`deploy-pages.yml` runs on pushes to `main` and by manual dispatch on `main`.
Its build job also requires `docs-sources` approval. It runs the shared release checks before upload:

- check out `pydasc/pydasc.github.io`;
- configure Python and install `requirements-docs.txt`;
- collect sources at the manifest's immutable commit SHAs;
- validate the staged documentation and run tests;
- build with `mkdocs build --strict`;
- upload `site/` with the official Pages artifact action;
- deploy with the official Pages deployment action in the `github-pages` environment.

`update-source-locks.yml` runs weekly and by manual dispatch on `main`, after
`docs-sources` approval. It uses the same
short-lived, read-only GitHub App token as the check and deployment workflows to
acquire each fixed private upstream repository and fetch the exact content commit declared
by its candidate publication contract, and validates the complete candidate
before changing only `checkout_commit` values in `docs-manifest.yml`. A changed
candidate must pass tests, deterministic assembly, publication validation, the
strict build, link and accessibility checks, and the complete artifact scan.
Only then does the workflow create a branch and pull request. It never edits an
upstream repository, changes the file allowlist, merges, or deploys.

Store App credentials only in `docs-sources`, restricted to the exact `main`
branch (no tags) and required approval by trusted private-source maintainers.
Remove repository-level and accessible organization-level copies; workflow
conditions alone cannot protect secrets from branch writers. PR jobs do not use
this environment. See `docs/operations/github_app.md` for the migration and
approval procedure. The separate `github-pages` environment protects final
deployment, not source retrieval.

The repository setting **Actions → General → Workflow permissions → Allow GitHub
Actions to create and approve pull requests** must permit pull-request creation.
Approval remains a human publication decision: review the immutable commits and
content diff before merging an automated proposal.

All workflow defaults grant `contents: read`. Only the final Pages deploy job
adds `pages: write` and `id-token: write`; only the protected source-update proposal
job adds website contents/PR write permissions. The Pages concurrency group is
`pages` with cancellation disabled. Source App tokens remain read-only.

Pin every action to a reviewed commit SHA. Configure the repository's **Settings → Pages → Build and deployment → Source** to **GitHub Actions**. The workflow must not commit the built `site/` directory or use a `gh-pages` branch.

The repository workflow keeps Pages enablement disabled and cannot perform the
required administrative review. Before the first deployment, follow
`docs/operations/pages-deployment-checklist.md` to configure environment and
branch protection, inspect the first artifact, verify the site while signed out,
and rehearse the reviewed rollback procedure. Do not push or manually dispatch
the deployment workflow until that release is explicitly authorized.

## Security model

- The manifest is an allowlist, not a discovery mechanism.
- Production inputs are immutable commit SHAs.
- Source and destination paths are resolved and checked for containment.
- Symlinks, path traversal, absolute paths, duplicate destinations, and unsupported file types fail the build.
- Imported repositories are data only; their scripts, actions, plugins, and configuration are never executed.
- Deployment uses GitHub's short-lived OIDC credentials and minimal permissions.
- A strict build, link checks, and tests must pass before upload.

[AGENTS.md](AGENTS.md) is the canonical contributor/automation policy;
[Repository TODO](tasks/TODO.md) is the current task entry point.
The [refactoring execution record](docs/operations/refactoring-progress.md) records
local commits and checks. Dated plans and the
[4 October status record](docs/operations/document-status.md) are history, not
proof that later commits passed remote checks. CPU/GPU content promotion remains
separately blocked on publication approval; see
[its review task](tasks/CPU_GPU_PUBLICATION_REVIEW.md).

## License and attribution

The website's own license should be declared in this repository. Imported files retain their upstream copyright and license terms. Each generated document should identify its source repository, source path, and exact commit. Do not assume that public visibility alone grants republication rights.

The collector renders that publication record visibly at the start of every
imported page, including the owning project, controlled documentation status,
SPDX license identifier, source path, and immutable content commit. The same
values remain in the generated inventory for artifact review.

## Accessibility verification

The release pipeline applies semantic checks to every generated HTML page in
addition to strict MkDocs and link validation:

```bash
python scripts/validate_accessibility.py --site site
```

This gate checks document language and title, main and named navigation
landmarks, one level-one heading, unskipped heading order, image alternative-text
attributes, table headers, and unique element IDs. It complements—but does not
replace—manual keyboard, zoom, contrast, screen-reader, mobile, and print review.

DASC physics equations use native MathML inside locally owned accessible groups,
with descriptive labels, stable `eq-` anchors, visible CSS numbering, horizontal
overflow at narrow widths, and print-safe styling. No remote equation renderer
or font is downloaded. Validate authored equation references, citation-footnote
keys, and forbidden local paths with:

```bash
python scripts/validate_physics_docs.py --docs docs
```


### Interrupted collection recovery

Generated project directories and inventory are installed as one recoverable
transaction. A sibling `.docs.collection-lock/` directory rejects overlapping
writers; staging and backups reside on the output filesystem. Ordinary failed
preparation, replacement or inventory writes restore the previous generation.
This is a rollback protocol, not simultaneous multi-directory atomicity.

After a hard process termination or failed rollback, keep the lock directory.
Stop all collectors before inspecting its journal, `previous/` and `next/`.
The only managed destinations are `pydasc/`, `dasc/` and
`generated-inventory.json`; authored pages must remain untouched. Restore each
available `previous/` entry to its matching destination, and remove newly
installed managed entries that had no previous counterpart. A `committed`
journal means the new generation completed; verify it before discarding backups.
Do not infer success from the presence of an inventory alone. Remove the lock
only after restoring/verifying one complete generation, then rerun the full
release checks. Power-loss durability and hostile concurrent filesystem mutation
are not guaranteed by this protocol; ambiguous recovery must fail closed.


Source-lock updates preserve plain/single-quoted/double-quoted SHA formatting
and unrelated comments. Ambiguous aliased/anchored lock edits are rejected.
The complete candidate must pass contract checks before a same-directory atomic
replacement; stale content, changed file identity or an active update lock stops
the write. Explicit manifest symlinks retain their link and update only the
verified target. An interrupted `.manifest-name.update-lock/` must be inspected
and removed only after confirming no updater is running; temporary files are not
publication approvals.


Scan the complete built artifact locally with
`python scripts/validate_artifact.py --site site`. The same command runs before
Pages upload and source-update proposals. It checks all regular artifact files,
including binary assets, rejects symlinks/special files and files over 5 MiB,
and applies the collector's credential/private-content policy to authored output
too. Diagnostics identify the relative filename and category while redacting the
matched payload. Imported Markdown retains its separate, stricter resource and
publication-contract checks.


For repository Python formatting, install the pinned `requirements-dev.txt`
and run `python -m ruff format --check scripts tests`. Apply formatting with
`python -m ruff format scripts tests`. The formatter configuration is in
`pyproject.toml`; site builds continue to use `requirements-docs.txt`.


CI source acquisition is shared by `scripts/acquire_sources.py`. Its explicit
`--mode reviewed` fetches exact website locks; `--mode candidate` fetches source
heads only for the separately validated update-proposal workflow. Destinations
must be fresh and outside docs. `SOURCE_TOKEN` is passed through ephemeral Git
configuration, with credential helpers and hooks disabled; it is never stored
in repository configuration. Failed/partial acquisition directories must be
inspected and replaced with a fresh destination rather than reset in place.


Browser checks are documented in [the local browser guide](docs/operations/browser-checks.md).
Full protected CI releases require `--browser-tests`; local Python-only checks
remain available before the separate browser runtime is installed.


The source-free filesystem CI subset runs on Linux and macOS. Locally, run:

```bash
python -m pytest -q -rs tests/test_output_safety.py tests/test_input_safety.py \
  -k 'case_alias or filesystem_containment or regular_reader or output_identity'
```

Case-sensitive and case-insensitive checks report explicit skips where a filesystem
cannot exercise them. Local macOS success does not assert that the new Linux CI job
has run; remote results require a later authorized push/run.

Dependency intent, pins, clean reproduction and deliberate upgrades are described in
[dependency maintenance](docs/operations/dependency-maintenance.md).

### Reconciled compatibility checks

The [dated compatibility review](tasks/COMPATIBILITY_REVIEW.md) records the parallel
remote work. Its candidate-collection gate, complete directory snapshots and
site/source-overlap checks are retained within the current modules. A candidate
must collect successfully before any lock replacement. Site output cannot overlap
source checkouts or publication inputs, and determinism includes empty directories.
The shared release runner preserves `check_release(root, pydasc, dasc)` for Python
callers in addition to the documented CLI. Scientific source locks are unchanged.
