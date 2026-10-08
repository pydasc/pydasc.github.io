# Browser and theme compatibility checks

The reviewed baseline is Material 9.7.7, Playwright 1.62.1 and Node 24.19.0.
`package-lock.json` pins the browser harness dependency tree; Playwright selects
its Chromium revision. Install with `npm ci --ignore-scripts`, then
`npx --no-install playwright install chromium` (CI adds `--with-deps`).
Run `python scripts/check_release.py --pydasc PATH --dasc PATH --browser-tests`.
For an already validated build, `npm run test:browser` repeats only browser checks.

The harness serves the actual built site on loopback using an ephemeral port,
creates a fresh browser profile and blocks external requests. It exercises
project-footer boundaries, keyboard Enter/Space/Escape, focus return, real narrow
screen table overflow and print CSS. The drawer consumes Enter/Space propagation so Material's global Enter handler
cannot activate it a second time. A missing keyboard handler fails behavior,
not just a source-string assertion. It does not test remote Pages permissions.
`DASC_BROWSER_EXECUTABLE` can explicitly select a local Chrome executable; such
a run reports its version and is distinct from CI's pinned Chromium run.
`DASC_BROWSER_REPORT_DIR` optionally saves screenshots outside the release site.

## Theme ownership

`partials/header.html` supplies project identity and the keyboard drawer control;
`partials/footer.html` supplies project-boundary navigation; `partials/content.html` supplies breadcrumbs and preserves Material content includes;
`404.html` supplies the reviewed not-found page.
`mkdocs_hooks.on_env` makes two guarded substitutions in Material's nav-item template
to reference text-bearing labels. It fails on template drift instead of silently
copying a full upstream template. Review these integration points on every theme
upgrade. Instant navigation is not enabled; do not assume event lifecycle coverage
for it without a separate change and new browser tests.

## Manual release checklist

- Inspect desktop and mobile layout at 200% zoom and with keyboard focus visible.
- Check dark/high-contrast and reduced-motion preferences with assistive technology.
- Read representative MathML equations with a screen reader; check meaning/order.
- Inspect a printed physics page and the wide claim matrix for clipping.
- Record browser/OS/assistive-tool versions, reviewer and date after doing the review.

Automated browser/static tests are a bounded regression suite, not an accessibility
certification. No manual sign-off is inferred from their success.
