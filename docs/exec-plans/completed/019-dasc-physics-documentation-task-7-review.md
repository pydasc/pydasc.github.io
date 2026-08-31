# Task 7 review: complete DASC physics section

## Review disposition

**Conditional; not release-clean.** No critical model-boundary, sign, causality,
or false-validation defect was found. DASC-REV-001 is closed after hands-on
Chrome verification and a follow-up runtime-wrapper correction. DASC-REV-002
now has an automated fix and requires browser/screen-reader confirmation.
DASC-REV-003 now has an automated fix and requires browser/screen-reader
confirmation. One medium provenance issue, one low-severity stale-workflow
issue, and one high-priority manual-test gap remain.

This was a review-only task. No disputed physics or reported defect was silently
repaired. No source lock, imported file, manifest, deployment setting, or
publication status changed.

## Severity-ranked findings

### High — DASC-REV-001: wide tables can be clipped on mobile and at high zoom

- **Pages/URLs:**
  - `docs/dasc-method-selection.md`,
    `https://chongshikpark.github.io/dasc.github.io/dasc-method-selection/`
  - `docs/dasc-validation-matrix.md`,
    `https://chongshikpark.github.io/dasc.github.io/dasc-validation-matrix/`
  - `docs/dasc-reproducibility.md`,
    `https://chongshikpark.github.io/dasc.github.io/dasc-reproducibility/`
  - also every other DASC Markdown table.
- **Evidence:** generated tables are bare `<table>` elements, not children of
  `.md-typeset__table`. At `docs/stylesheets/readthedocs.css:547`, horizontal
  overflow is assigned only to `.md-typeset__table`; at lines 554–557 bare
  tables become `width: max-content`. The page containers suppress horizontal
  overflow, so the widest columns have no local scroll surface.
- **Impact:** method-selection and validation evidence can become unreadable or
  unreachable on a narrow viewport or at 200% zoom. Keyboard users also lack a
  focusable, labeled scroll region.
- **Proposed owner:** portal presentation/accessibility owner.
- **Proposed correction:** wrap every table in a labeled, keyboard-scrollable
  container, or apply overflow directly to a suitable block wrapper generated
  consistently by MkDocs. Preserve header semantics and add a visible focus
  style.
- **Resolution:** implemented after the review with a deterministic MkDocs hook
  that wraps every content table in a named `role="region"`, `tabindex="0"`
  scroll container. CSS supplies local horizontal overflow, overscroll
  containment, a visible focus indicator, narrow scrollbars, and print behavior.
  The semantic validator rejects unwrapped or incorrectly attributed tables. A
  hands-on Chrome retest found that Material adds `.md-typeset__scrollwrap` and
  `.md-typeset__table` at runtime, leaving overflow on an unfocusable nested
  element. The CSS now makes those runtime wrappers non-scrolling and assigns
  the complete scroll range to the named outer region.
- **Retest:** **Closed.** Chrome testing on the method-selection, validation-
  matrix, and reproducibility pages confirmed that every affected table has a
  horizontal scroll range, receives keyboard focus, and moves with arrow keys.
  The document viewport itself does not overflow at 390 px. Equivalent 720 px
  and 360 px layout-pressure checks cover the 200% and 400% reflow cases. The
  narrowest method table exposed a 328 px viewport over a 2733 px scroll range,
  and keyboard input changed its scroll position. Regression, strict-build,
  site, and semantic-accessibility checks also pass. Forced-color, screen-reader,
  and print-preview testing remain tracked by DASC-REV-GAP-001 rather than this
  table-clipping defect.

### High — DASC-REV-002: MathML encodes volume elements with the exponent on the variable

- **Pages/equations:**
  - `docs/dasc-conventions.md:31`, `#eq-total-charge`
  - `docs/dasc-conventions.md:43`, `#eq-fourier-pair`
  - `docs/dasc-tgf-free-space-poisson.md:23`, `#eq-tgf-green-convolution`
  - `docs/dasc-potentials-fields-dynamics.md:37`, `#eq-coulomb-potential`
- **URLs:** corresponding `dasc-conventions/`,
  `dasc-tgf-free-space-poisson/`, and
  `dasc-potentials-fields-dynamics/` equation anchors.
- **Evidence:** MathML uses `<mi>d</mi><msup><mi>V|r|k</mi><mn>3</mn></msup>`,
  which represents dV³, dr³, or dk³. The search index exposes the same strings
  (`dV3`, `dr3`, `dk3`), while surrounding prose and dimensional checks require
  d³r or dV.
- **Impact:** the structured equation and assistive/search text state a
  dimensionally different measure from the intended three-dimensional volume
  element. This is not merely visual typography.
- **Proposed owner:** DASC physics documentation owner, with accessibility review.
- **Proposed correction:** encode a standard volume element consistently, such
  as `<msup><mi>d</mi><mn>3</mn></msup><mi>r</mi>` for d³r or `<mi>d</mi><mi>V</mi>`
  for dV, including primed source coordinates.
- **Resolution:** implemented after the review. The generic volume integral now
  uses dV; Cartesian Fourier and Coulomb measures use d³r and d³k; primed source
  measures attach the prime to **r**, not to the exponent. The physics validator
  and regression tests now reject the former dV³/dr³/dk³ MathML structure.
- **Retest:** **Automated checks passed.** Dimensional source review, equation
  validation, strict build, and semantic-accessibility checks pass. The rebuilt
  search index contains `d3r` and `d3k` and no `dV3`, `dr3`, or `dk3`. Rendered
  browser and screen-reader confirmation remains pending under
  DASC-REV-GAP-001 because no browser backend was available.

### Medium — DASC-REV-003: fixed-point notation is corrupted by Markdown emphasis

- **Page/section:** `docs/dasc-da-self-consistency.md:25`,
  `https://chongshikpark.github.io/dasc.github.io/dasc-da-self-consistency/#iterated-and-fixed-point-models`.
- **Evidence:** source text `x*(θ) satisfies x* = F(x*,θ)` renders as
  `x<em>(θ) satisfies x</em> = F(x*,θ)`. The fixed-point stars disappear or
  delimit an italic span, while the following MathML equation correctly uses x*.
- **Impact:** the prose definition of the fixed point is ambiguous and disagrees
  with its displayed derivative equation.
- **Proposed owner:** DA/TPSA documentation owner.
- **Proposed correction:** use inline MathML, escaped stars, or unambiguous
  Unicode notation consistently.
- **Resolution:** implemented after the review with inline MathML using the
  mathematical asterisk operator `∗`, avoiding Markdown delimiter syntax while
  preserving superscript fixed-point notation. A regression test rejects the
  former emphasis span and paragraph splitting.
- **Retest:** **Automated checks passed.** The generated sentence is one
  paragraph, its MathML contains no `<em>` markup, and search extraction reads
  `x∗(θ) satisfies x∗=F(x∗,θ)`. Strict-build, site, physics, and semantic-
  accessibility checks pass. Hands-on copied-text and screen-reader inspection
  remains pending under DASC-REV-GAP-001.

### Medium — DASC-REV-004: validation-matrix implementation evidence is not directly traceable

- **Page/section:** `docs/dasc-validation-matrix.md:17–35`,
  `https://chongshikpark.github.io/dasc.github.io/dasc-validation-matrix/`.
- **Evidence:** the page gives locked commit SHAs, but component and test cells
  contain abbreviated code text such as `space_charge_vgf.py` and
  `test_vgf_kernel.py`, not links to the exact repository, path, and immutable
  commit. Several test descriptions do not state a complete path.
- **Impact:** a reviewer cannot move directly from claim to immutable
  implementation/test evidence, and similarly named files are possible.
- **Proposed owner:** portal provenance and DASC validation owners.
- **Proposed correction:** link every component and named test/reference to its
  complete path at the locked PyDASC commit; retain the artifact-pending label.
- **Resolution:** implemented after the review. Every named PyDASC component,
  test, and reference now displays its complete repository-relative path and
  links to the exact locked commit. The small-hole and self-consistent-cavity
  rows retain their explicit evidence gaps rather than linking unrelated tests;
  all artifact-pending labels remain unchanged.
- **Retest:** **Automated checks passed.** Regression coverage requires complete
  path labels, the locked 40-character SHA, and immutable `blob` or `tree`
  targets, and rejects `main` or `master` links. The GitHub API confirmed that
  every linked path exists in the public PyDASC tree at the locked revision.

### Low — DASC-REV-005: completed task numbers remain in reader-facing physics prose

- **Pages/sections:**
  - `docs/dasc-potentials-fields-dynamics.md:72–76`, “Decision required before a
    shared Hamiltonian equation”
  - `docs/dasc-eigenmode-fields.md:50–54`, “Force and self-consistent dynamics”
- **Evidence:** published prose says “Task 3 must,” “Task 4 must,” and “Task 5
  treats,” although Tasks 3–5 now have permanent linked sections.
- **Impact:** readers encounter internal workflow history instead of the current
  scientific status and may infer that completed derivations are still absent.
- **Proposed owner:** DASC documentation editor.
- **Proposed correction:** replace task numbers with links to the completed TGF,
  eigenmode, and DA/TPSA pages while preserving unresolved decisions.
- **Resolution:** implemented after the review. The shared dynamics page now
  links to the permanent TGF kick and causal cavity force sections, and the
  eigenmode field page links to the permanent DA/TPSA eigenmode pipeline. The
  unresolved normalization, trajectory-feedback, and differentiability
  boundaries remain explicit.
- **Retest:** **Automated checks passed.** A regression test scans every
  reader-facing `dasc-*.md` physics page and rejects numbered-task and
  future-task language.

## Manual review gap

### High priority — DASC-REV-GAP-001: interactive accessibility review unavailable

Chrome later became available and closed DASC-REV-001's mobile, keyboard, and
high-zoom layout checks. Screen-reader math, copied equation text, forced-color
contrast, and print-to-PDF remain **not tested**. Static HTML and CSS inspection
cannot close those requirements. This remaining gap is especially important for
DASC-REV-002's structured mathematical output.

- **Proposed owner:** accessibility reviewer with a supported browser and screen
  reader.
- **Retest:** **Blocked by unavailable browser backend**, not by repository code.

## Checks that passed

### Physics and content

- The home page/project chooser and DASC overview remain project- and
  physics-first rather than paper-first.
- TGF and eigenmode formulations state distinct domains, boundaries, time
  models, sources, fields, and applicability limits.
- DA/TPSA, energy consistency, Lie/canonical structure, and symplecticity are
  described as separate properties.
- Assumptions precede the reviewed TGF and cavity equations.
- Planned aperture, self-consistent cavity, DA, convergence, performance, and
  physical results are not presented as validated results.
- The method comparison and validation matrix agree on the prescribed-source
  cavity boundary and the absence of a public allowlisted result package.
- The matrix explicitly leaves a self-consistent symplectic cavity map open.

### Equations, citations, provenance, and search

- 40 displayed equations have unique stable IDs and accessible group labels;
  local equation references and footnote keys resolve.
- Direct DASC source links use commit
  `94033eae4d8eac81f4c42c41f6cfba69e1cd2a25`; local exact-commit checkouts
  contain the referenced source files.
- The locked PyDASC checkout at
  `0506b8a9feb75813ae979f0c1c25a307b21096d2` contains the components and tests
  summarized by the matrix. The public GitHub API exposes the same files at that
  exact immutable tree, and every matrix target was checked against it.
- The generated search index contains space charge, TGF, truncated Green
  function, eigenmode, retarded Green function, DA, TPSA, Lie map,
  symplecticity, and causality.

### Navigation and static accessibility

- Navigation is explicit; all DASC physics pages are in `mkdocs.yml`.
- Previous/next footer links stay inside DASC at the project boundaries.
- The secondary table-of-contents rail is hidden, preserving the requested
  two-column navigation/article layout.
- Generated pages pass language/title, landmark, H1, heading-order, image-alt,
  table-header, and unique-ID checks.
- Equations have narrow-screen overflow and print break rules; reduced-motion
  and forced-color rules are present.
- No private/local filesystem path, excluded task source, credential, unapproved
  figure, or unexpected generated file appears in the built artifact.

## Automated verification

- 34 tests passed after DASC-REV-001 through DASC-REV-005 regression coverage
  was added.
- Physics equation, anchor, citation, and forbidden-path validation passed.
- Exact-lock source collection and publication-boundary validation passed.
- Repeated source assembly produced no generated-content diff.
- `mkdocs build --strict` passed without warnings.
- Site link/presentation and semantic-accessibility validation passed.
- Required search terms were present in the generated search index.
- The built artifact scan found no local filesystem path or excluded task file.
- `git diff --check` passed; the only worktree addition from this review is this
  excluded execution report.

## Release recommendation

Complete the hands-on retests of the DASC-REV-001 through DASC-REV-003 fixes and
run the remaining interactive review in DASC-REV-GAP-001 before calling the
DASC physics section release-clean. Numerical physics claims remain artifact-
pending exactly as stated in the validation matrix.
