# AGENTS.md

## Repository scope

This repository is the source for the DASC documentation website:

- Repository: `https://github.com/pydasc/pydasc.github.io`
- Published site: `https://pydasc.github.io/`
- Documentation sources:
  - `https://github.com/pydasc/pydasc`
  - `https://github.com/pydasc/dasc`

The site is a static Material for MkDocs project deployed with GitHub Actions and GitHub Pages. It presents a unified, Read-the-Docs-like documentation experience while keeping `pydasc` and `dasc` as the authoritative upstream repositories.

## Working rules

1. Treat upstream repositories as read-only inputs. Never push changes to `pydasc/pydasc` or `pydasc/dasc` from this repository's workflows or scripts.
2. Publish only files explicitly listed in `docs-manifest.yml`. Do not recursively copy an upstream `docs/` tree, README collection, notebook directory, generated API output, or repository root.
3. Reject manifest entries that are absolute paths, contain `..`, resolve through a symlink outside the source checkout, or target anything other than a regular file.
4. Do not publish secrets, credentials, private URLs, CI logs, build artifacts, test data, development notes, security reports, or files not intended for public distribution.
5. Pin third-party GitHub Actions to immutable commit SHAs. Pin Python dependencies in `requirements-docs.txt` to reviewed versions.
6. Give every imported document a destination below either `docs/pydasc/` or `docs/dasc/`. Hand-written portal pages belong directly below `docs/`.
7. Do not edit generated imported files in place. Change the upstream source or the manifest/transformation logic and regenerate them.
8. Preserve attribution and license notices. Do not import a file unless its license permits republication.
9. Use repository-relative links in authored Markdown. The collector must validate or rewrite imported relative links and images so they work at the destination.
10. Keep deployment least-privileged: `contents: read`, `pages: write`, and `id-token: write`; do not use long-lived deployment tokens.

## Expected layout

```text
.
├── .github/workflows/
│   ├── docs-check.yml
│   └── deploy-pages.yml
├── docs/
│   ├── index.md
│   ├── pydasc/
│   ├── dasc/
│   ├── assets/
│   └── overrides/
├── scripts/
│   ├── collect_docs.py
│   └── validate_docs.py
├── tests/
├── docs-manifest.yml
├── mkdocs.yml
├── requirements-docs.txt
├── AGENTS.md
└── README.md
```

`docs/pydasc/` and `docs/dasc/` are generated staging destinations. If generated files are committed, CI must verify that rerunning the collector produces no diff. Otherwise, generate them only in CI and exclude them from source-control checks as documented in `README.md`.

## Manifest contract

`docs-manifest.yml` is the publication boundary. Use a structure equivalent to:

```yaml
schema_version: 1
sources:
  pydasc:
    repository: pydasc/pydasc
    ref: "<reviewed full commit SHA>"
    files:
      - source: README.md
        destination: pydasc/index.md
  dasc:
    repository: pydasc/dasc
    ref: "<reviewed full commit SHA>"
    files:
      - source: README.md
        destination: dasc/index.md
```

Every `ref` used for production must be a reviewed 40-character commit SHA. Branches may be accepted only by an explicit local preview option and must never be used by deployment. Each destination must be unique and remain inside `docs/<source>/`.

## Implementation expectations

- Use Python's standard path APIs to resolve and contain paths; string-prefix checks are insufficient.
- Copy bytes deterministically and preserve only necessary metadata. Do not execute upstream code or install upstream packages to collect Markdown.
- Clone or download source repositories into a temporary directory outside `docs/`; use shallow, commit-specific fetches where practical.
- Make collection fail closed: an unknown manifest key, missing source, duplicate destination, invalid source/ref, unsafe link, or unsupported file type must stop the build.
- Prefer Markdown, approved images, and explicitly required downloadable examples. Define allowed extensions in the collector and test them.
- Add a generated-file banner with source repository, source path, and commit SHA when the file type supports comments without affecting rendering.
- Configure `site_url` as `https://pydasc.github.io/` and `repo_url` as `https://github.com/pydasc/pydasc.github.io`.
- Keep navigation explicit in `mkdocs.yml`; do not expose a file merely because it exists under `docs/`.
- Use `mkdocs build --strict` in all checks and before deployment.

## Required verification

Before considering a change complete, run the equivalent of:

```bash
python -m pytest
python scripts/collect_docs.py --manifest docs-manifest.yml --output docs
python scripts/validate_docs.py --manifest docs-manifest.yml --docs docs
mkdocs build --strict
git diff --exit-code
```

Tests must cover path traversal, absolute paths, symlink escape, duplicate destinations, unpinned refs, missing files, disallowed extensions, link/image handling, deterministic output, and unexpected files in generated destination directories.

## Change discipline

- Keep changes narrowly scoped and explain any publication-boundary change in the pull request.
- Review additions to `docs-manifest.yml` as public releases of content.
- Never bypass a failing strict build or security validation to deploy.
- Do not commit `.venv/`, `site/`, temporary checkouts, caches, credentials, or GitHub tokens.
- Update `README.md` when commands, layout, publication policy, or deployment behavior changes.

