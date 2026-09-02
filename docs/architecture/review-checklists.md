# Documentation review checklists

Use these checklists before adding a page to public navigation and again when inspecting a release artifact. Record failures and owner decisions; do not waive a check by silently editing technical meaning.

## Accessibility review

### Structure and navigation

- [ ] The page has one descriptive level-one heading.
- [ ] Heading levels form a logical hierarchy without skipped levels used for visual styling.
- [ ] Link text describes its destination or action without relying on surrounding text.
- [ ] Repeated navigation is consistent, and the current project and section are clear.
- [ ] All interactive elements are reachable and operable by keyboard in a logical focus order.
- [ ] Focus indicators are visible against each supported color scheme.
- [ ] The page remains usable at narrow mobile widths and at 200% browser zoom.

### Images, color, and media

- [ ] Informative images have concise alternative text conveying their purpose.
- [ ] Decorative images use empty alternative text or an equivalent presentation treatment.
- [ ] Charts and diagrams have a text explanation or accessible data equivalent.
- [ ] Text and meaningful graphical elements meet the project’s reviewed contrast target.
- [ ] Meaning is not communicated by color alone.
- [ ] Motion or animation is avoidable and respects reduced-motion preferences, if present.

### Technical material

- [ ] Equations have surrounding prose, defined symbols, and a readable text or MathML representation where supported.
- [ ] Tables have descriptive headers, simple structure where possible, and a caption or introduction explaining their purpose.
- [ ] Code blocks identify the language where useful and remain horizontally usable on mobile.
- [ ] Code examples do not rely on color alone and include descriptive context before or after the block.
- [ ] Keyboard users can access copy controls without losing their reading position.
- [ ] Footnotes, citations, and back-links are keyboard accessible and understandable out of context.

## Content and publication review

### Identity and scope

- [ ] The page clearly identifies PyDASC or DASC.
- [ ] The applicable version, release, or immutable source revision is visible.
- [ ] The page purpose matches its navigation category.
- [ ] The text does not blur the distinction between the projects or their interfaces.
- [ ] Any prerequisites and intended audience are stated.

### Accuracy and scientific context

- [ ] Technical meaning matches the reviewed upstream source.
- [ ] Capabilities, performance, validation, and scientific conclusions have explicit reviewed evidence.
- [ ] Scientific limitations, assumptions, uncertainty, and applicability boundaries are visible where relevant.
- [ ] Validated and Unvalidated labels follow [the controlled status rules](status.md).
- [ ] Equations, units, symbols, tables, and figures were checked against the source.
- [ ] Examples distinguish illustrative use from validated results.
- [ ] No branding, affiliation, contact, approval, or support claim was inferred.

### Provenance and rights

- [ ] The source repository, source path, and exact commit are recorded.
- [ ] The source link resolves to the immutable revision.
- [ ] The edit link targets the authoritative repository rather than a generated portal copy.
- [ ] Redistribution permission and all required copyright/license notices are present.
- [ ] Citation instructions reproduce only approved upstream guidance.
- [ ] Release links identify the correct project and reviewed release.
- [ ] Third-party images, data, and quotations have documented rights and attribution.

### Security and privacy

- [ ] The file is individually allowlisted; no directory-wide assumption was used.
- [ ] No credential, token, private URL, local filesystem path, private issue, internal review, CI log, raw data, cache, or build artifact appears.
- [ ] Links and images resolve after relocation and stay within the approved remote-link policy.
- [ ] Downloads are explicitly approved, bounded in size, and have a reviewed public purpose.
- [ ] Notebook or executable output is absent unless a separate reviewed process approved it.

### Presentation and release artifact

- [ ] Navigation contains the page explicitly and under the correct project.
- [ ] Desktop and mobile rendering were inspected.
- [ ] Light and dark color schemes were inspected where both are supported.
- [ ] Search results identify the project and do not expose excluded pages.
- [ ] Code, equations, tables, images, admonitions, and citations render without strict-build warnings.
- [ ] Routes and assets work from the organization Pages root (`/`) without a project-site subpath.
- [ ] Superseded content points to its reviewed replacement.

## Review outcome

Record the reviewed commit, artifact checksum or build identifier, reviewer, date, failed checks, owner decisions, and retest evidence. A strict build proves site consistency; it does not by itself prove accessibility, technical correctness, redistribution permission, or scientific validation.
