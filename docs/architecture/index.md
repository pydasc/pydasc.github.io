# Documentation information architecture

Status: Draft architecture

This document defines the intended structure of the DASC documentation portal. It is a design contract for later tasks, not an approval to publish upstream files. The publication manifest remains the only content allowlist.

## Fixed identities

- Portal repository: `https://github.com/pydasc/pydasc.github.io`
- Published organization-site URL: `https://pydasc.github.io/`
- PyDASC source repository: `https://github.com/chongshikpark/pydasc`
- DASC source repository: `https://github.com/chongshikpark/dasc`

All portal URLs and assets must work from the organization Pages root (`/`). Authored site links must be repository-relative rather than tied to a project subpath.

## Audience paths

The first user choice is the project. The portal must not imply that PyDASC and DASC have interchangeable installation, interfaces, versions, release schedules, or support policies.

```text
Home
├── Choose a project
│   ├── PyDASC path
│   └── DASC path
├── PyDASC
│   ├── Overview
│   ├── Installation
│   ├── Guides
│   ├── Examples
│   ├── API and reference
│   └── Contribute
├── DASC
│   ├── Overview
│   ├── Concepts
│   ├── Guides
│   ├── References
│   └── Contribute
└── Portal contribution guidance
```

Only pages backed by reviewed, explicitly allowlisted material may enter the public navigation. Missing approval produces a clearly documented placeholder in planning records, not an invented public page.

## Shared portal pages

### Home

Purpose:

- identify the portal as a shared presentation layer;
- explain that the two upstream repositories remain authoritative;
- provide an immediate, descriptive route to the project chooser;
- show the source revision or documentation snapshot context when imported content is present.

The home page must not make scientific, performance, affiliation, or validation claims that lack reviewed source evidence.

### Choose a project

Purpose:

- state the reviewed distinction between PyDASC and DASC;
- ask users to choose by interface, workflow, and documentation need;
- route to each project overview and installation or starting page;
- keep project names and repositories visible at the decision point.

Until source contracts provide reviewed distinctions, this page may identify repository ownership and available documentation categories only. It must not infer capabilities from project names.

### Portal contribution guidance

Purpose:

- route code and source-documentation changes to the owning upstream repository;
- route portal presentation and publication-boundary changes to the website repository;
- explain that generated imports are not edited in place.

## PyDASC section contract

| Page | User question | Required reviewed basis |
| --- | --- | --- |
| Overview | What is this project, and is it the one I need? | Approved upstream overview and limitations |
| Installation | How do I install a supported version? | Approved version-specific installation material |
| Guides | How do I complete an approved workflow? | Individually approved guides with prerequisites |
| Examples | What does an approved usage pattern look like? | Individually approved, non-secret examples and execution status |
| API and reference | What interfaces are documented and stable? | Approved API/reference source and stability/version metadata |
| Contribute | Where should changes and issues go? | Reviewed upstream contribution and repository links |

If a category has no approved source content, omit it from public navigation. Do not replace it with synthesized technical guidance.

## DASC section contract

| Page | User question | Required reviewed basis |
| --- | --- | --- |
| Overview | What is this project, and is it the one I need? | Approved upstream overview and limitations |
| Concepts | Which reviewed concepts are necessary to understand the project? | Approved conceptual documentation and citations where required |
| Guides | How do I complete an approved workflow? | Individually approved guides with prerequisites |
| References | Where are defined interfaces, formats, or supporting references? | Approved reference sources and version metadata |
| Contribute | Where should changes and issues go? | Reviewed upstream contribution and repository links |

If a category has no approved source content, omit it from public navigation. Do not infer conceptual or scientific material from repository files that lack publication approval.

## Page-level context and links

Every imported page must expose or link to the following context, using manifest metadata or generated provenance rather than hand-maintained guesses:

| Context | Placement | Rule |
| --- | --- | --- |
| Project | Page header or provenance block | Clearly say PyDASC or DASC |
| Documentation status | Near the title | Use only the controlled vocabulary and evidence in [Documentation status](status.md) |
| Source | Provenance block | Link to the exact source path at the immutable commit |
| Edit | Provenance block | Link to the authoritative upstream file; never imply generated portal files are authoritative |
| License | Provenance block or project metadata page | State the reviewed redistribution basis; absence blocks publication |
| Citation | Page context or project metadata page | Include only upstream-approved citation instructions |
| Release/version | Page context | Link only to a reviewed release or exact source revision |
| Contribution | Section landing page and footer where useful | Route to the repository that owns the content |

Repository landing links may target the canonical repositories above. Source, edit, release, citation, and license URLs must come from reviewed publication metadata instead of branch-name assumptions.

## Navigation rules

- Keep `mkdocs.yml` navigation explicit.
- A file existing below `docs/` does not approve or expose it.
- Keep PyDASC and DASC as separate navigation sections.
- Use descriptive labels; avoid repeated generic labels such as “Learn more.”
- Provide breadcrumbs or equivalent navigation context through the theme.
- Do not add Downloads or About pages until reviewed public material establishes their purpose, content, license, and ownership.
- Internal architecture and execution-plan files are excluded from the built site.

## Unresolved owner decisions

- The reviewed wording that distinguishes PyDASC from DASC for the project chooser.
- Which pages and assets each upstream source contract approves for the first release.
- Whether either project has approved installation, citation, release, contribution, or known-limitations pages.
- The redistribution basis for every imported artifact, including DASC material for which no license has yet been confirmed.
- Whether generated API documentation or executable examples will be approved in a later task.
- Whether Downloads or About pages have sufficient reviewed public support.
- Whether the public site should display status labels on every page or only where status could be misunderstood.

These decisions must remain unresolved until supported by owner review or an approved upstream publication contract.
