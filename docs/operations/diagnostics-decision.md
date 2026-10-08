# WEB-REF-24 — diagnostics review

## Decision

Keep the small existing command-line interfaces. Do not introduce a diagnostic
registry, plugin framework or JSON failure protocol in this refactoring.

The shared release runner now reports the failed stage and stops immediately.
Individual validators already emit `error:` with the relevant relative artifact
path/context; artifact scanning reports the category while redacting the matched
payload. Acquisition deliberately suppresses transport stderr and token content.
The typed publication exceptions preserve the special unapproved-candidate outcome
used by `update_source_locks.py --skip-unapproved`.

No workflow or local tool consumes structured diagnostic output. A schema would
create another compatibility obligation without eliminating an observed failure
mode. Preserve documented flags and exit outcomes. If a release dashboard or editor
integration later needs structured failures, define that consumer's minimal fields
first (stage, rule, relative path, message) and add redaction/failure tests alongside it.

## Verification and limits

Reviewed the entry points in collect_docs, validate_docs, validate_physics_docs,
validate_site, validate_accessibility, validate_artifact, acquire_sources,
update_source_locks and check_release. The existing failed-stage, redaction and
skip-outcome regressions remain applicable; no executable behavior changed here.
This decision does not assert that arbitrary user-supplied filenames can never
contain sensitive text or that tracebacks from every third-party tool are normalized.

Result: conditional task evaluated; additional diagnostics machinery deferred as
per the task's explicit no-consumer guardrail.
