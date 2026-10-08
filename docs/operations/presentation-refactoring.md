# WEB-REF-26 — sidebar foreground ownership

The browser screenshots exposed a concrete style-ownership defect: Material's
more specific section-label selector inherited its dark default foreground on the
site's dark sidebar. The existing explicit link color did not govern that label.
This justified a small correction within the existing design, rather than a
stylesheet split or visual redesign.

`--dasc-sidebar-text` now owns the existing #d9d9d9 foreground, replacing three
repeated declarations. The sidebar scopes Material's `--md-default-fg-color--light` to
that token so project labels and links agree. No color was invented and no layout,
overflow, reduced-motion, forced-color or print rule was removed. Browser tests
now check computed foreground/background contrast for visible desktop section
labels in addition to keyboard/mobile/table/print behavior. That bounded check is
not a complete accessibility certification.

The single stylesheet remains sectioned by responsibility. The generic built-link
checks already use DocumentIndex, while validate_site's short required-token map
remains a deliberate brand contract. Splitting either into more files, or aliasing
semantically separate status/accent colors, has no demonstrated benefit here.

Result: the concrete foreground duplication/inheritance issue is fixed; broader
CSS reorganization is deferred. Manual zoom, assistive MathML and print review
remain in browser-checks.md. Scientific content and approved source identities
are unchanged.
