# Documentation and task status — 4 October 2026

Internal maintenance record, excluded from the public site by the existing
operations/ exclusion. The public pages describe reviewed snapshots and
conceptual formulations, not the latest private manuscript or campaign status.

## Completed and open work

- [x] Website scaffold, deterministic allowlisted collection, architecture and
  physics documentation Tasks 0–7: implementation/review records 001–019.
- [x] Dependency and CI refresh: record 020; latest check and Pages jobs pass.
- [x] Verify remote Documentation checks and Pages deployment at 95de4c6.
- [ ] Review/promote newer upstream documentation through a new immutable lock
  and compatible publication contract. Current local upstream edits are not
  part of the website's approved source snapshot.
- [ ] Repeat release-specific human accessibility/content checks as needed;
  completed historical checks do not permanently complete reusable checklists.
- [ ] Complete any remaining branch/environment governance decisions and
  release approvals; successful jobs do not prove every configuration rule.

[Repository TODO](../../tasks/TODO.md) is the current task register.
[The administrator checklist](pages-deployment-checklist.md) records observed
completion separately from actions that still need direct verification.
Old prompts and completed execution plans remain historical, including earlier
repository names, pending deployment notes and original source identities.

## Remote CI inspection

| Workflow | Commit | Observed result |
| --- | --- | --- |
| pydasc CI | `74fabb797a61d47328a24a9d685ccb9af755d7f7` | [Success](https://github.com/pydasc/pydasc/actions/runs/37190450812) |
| dasc repository/scientific checks | `4b49c5f93b9ccabb621f849f939e4efabd35ef17` | [Success](https://github.com/pydasc/dasc/actions/runs/37209940722) |
| Website Documentation checks | `95de4c6757f7f1189a04f69047d97f9e5a9a9944` | [Success](https://github.com/pydasc/pydasc.github.io/actions/runs/37187497171), docs and source-docs |
| Website Pages deployment | `95de4c6757f7f1189a04f69047d97f9e5a9a9944` | [Success](https://github.com/pydasc/pydasc.github.io/actions/runs/37187497220), build and deploy |
| Source-update proposal, latest observed scheduled run | Prior revision, 28 September 2026 | [Success](https://github.com/pydasc/pydasc.github.io/actions/runs/36405649356); not re-executed for current edits |

The website source-access approvals for the two 4 October runs are recorded
under chongshikpark in docs-sources. The deployment artifact SHA256 is
`a886c16f6457a54b10a318f6dc8c0423f2b37c50990fc1c27f2c3a3a99f5d399`.
Elapsed workflow time includes approval waiting and is not build performance.
No new approval, dispatch, commit, push or deployment was performed here.
The user pushed dasc 4b49c5f during this review; its new repository and scientific
jobs both passed. These uncommitted companion-document edits still require
their own future CI.

## Source boundary and local verification

The website locks remain pydasc `0506b8a9feb75813ae979f0c1c25a307b21096d2`
and dasc `94033eae4d8eac81f4c42c41f6cfba69e1cd2a25`. Their publication
content commits are respectively `dab60df7f8d1cc5f0338fbe1c3885c6624af1a33`
and `0960f639055c4fe60029175ad603d1f52dc2fc53`. The observed deployment URL is
[the public documentation site](https://pydasc.github.io/). Imports are regenerated
only from those exact local checkouts through the collector; no generated
page is edited manually. The older docs/SIMULATION_WORKFLOW.md import remains
correct at its pin even though the active upstream workflow moved to tasks/.

The inventory beside this record lists every tracked docs/ and tasks/ item
and generated staging document with its disposition/hash. Current local
checks are recorded in execution record 021. Internal status/inventory files
stay excluded from the public build. The old website .venv is documented as
stale; verification uses the isolated pinned environment from record 020.
