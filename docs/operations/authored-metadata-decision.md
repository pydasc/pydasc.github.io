# WEB-REF-23 — authored navigation and metadata decision

The concrete publication gap is that an unlisted authored Markdown file can be
built by MkDocs even when it is absent from explicit navigation. The `on_files`
hook now rejects included documentation pages missing from `mkdocs.yml` navigation,
using MkDocs's own file inclusion decisions. Existing internal exclusions remain
honored. This check runs for local previews and strict release builds alike.
It covers imported pages too without changing the upstream manifest boundary.

Reviewed metadata ownership remains deliberately simple:

| Information | Owner / authoritative source |
| --- | --- |
| Imported project, commit, license, approval and status | Source contract and website manifest; validated inventory |
| Page inclusion, project grouping and ordering | Explicit `mkdocs.yml` navigation |
| Equations and local references | Authored physics pages; rendered reference validator |
| Physical validity, evidence scope and caveats | Page-specific reviewed narrative and validation matrix |

A second front-matter/claim registry is deferred: the existing five imports already
have typed provenance and the authored scientific prose has no single mechanically
interchangeable claim set. Copying it into a registry would add synchronization
work without proving semantic agreement. Future repeated fields need explicit
content-owner review before centralization. The hook does not infer scientific
validity, create status claims, rewrite equations or promote upstream material.

Result: navigation safeguard implemented; optional scientific-metadata registry
evaluated and deferred. The existing immutable evidence/provenance and physics-link
checks remain authoritative within their documented scope.
