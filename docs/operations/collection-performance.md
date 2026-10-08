# WEB-REF-25 — collection profile and optimization decision

Measured locally on 8 October 2026, macOS 26.7.1 x86_64,
Python 3.13.16 and the unchanged reviewed dependency pins. The collector code is
unchanged from WEB-REF-23. [Raw measurements](collection-profile.json) contain
five unprofiled durations and a separate instrumented run for each workload.

| Workload | Median collection + digest comparison | Traced Python peak | Process RSS high-water mark |
| --- | --- | --- | --- |
| approved | 1.343 s | 6.06 MiB | 36.53 MiB |
| synthetic | 2.207 s | 6.68 MiB | 43.78 MiB |

## Reproduction protocol

1. Use the website's unchanged docs-manifest.yml and its exact approved local
   source checkouts. Import only the website's collect_docs.assemble function.
2. For the approved workload, assemble into an isolated temporary output directory
   five times. Time each call plus a SHA-256 comparison of all generated files and
   inventory against the approved baseline. Do not include source copying in timing.
3. For the synthetic workload, copy both entire approved checkouts into temporary
   storage. Add 1,000 untracked 4-KiB files and ten untracked 1-MiB files per checkout
   under a synthetic-profile-inputs directory (2,020 extra files, about 27.8 MiB
   total). Keep the five-file publication allowlist and Git commits unchanged.
   Repeat the five measurements. Never add these synthetic files to real sources.
4. Run one additional assembly per workload under cProfile and tracemalloc. Record
   Git inspections, tree snapshots, Markdown conversions, approval and publication
   timings/calls, traced Python peak, and resource.getrusage(RUSAGE_SELF).ru_maxrss.
   macOS reports the latter in bytes; it is a process-lifetime high-water mark,
   not an independently reset per-phase allocation measurement.

Each workload uses 56 Git inspections, six tree snapshots (two repos at three
boundaries), 15 Markdown conversions and five rewrites. Profile timings are
inclusive and overlap; instrumentation substantially increases them, so do not
sum them or compare them directly with unprofiled wall times. These are local
repeated-run timings, not cold-cache, network, Linux or cross-machine claims.
All twelve assemblies reproduced the original approved document/inventory hashes.
No real upstream source was modified or executed.

## Decision

Do not add a persistent cache, parallel collector or reduced-integrity fast path.
The reviewed release uses two collections, about 2.7 seconds here, while its full
Python test suite alone takes about 144 seconds. Even eliminating collection would
save less than 2% of that release sequence. The acceptance bar for extra performance
complexity is a measured, repeatable 15% end-to-end release improvement with unchanged
adversarial/integrity behavior. The current workload cannot justify it through
collection optimization alone; the synthetic case also remains small.

The synthetic profile confirms source-tree hashing grows with unrelated checkout
size. If actual source growth makes it material, first evaluate a smaller exact
read-only source checkout or batched immutable Git reads. Any future candidate
needs before/after measurements, identical output, and mutation/race/symlink tests.
Do not replace byte checks with stat-only trust or reuse a cache across an unverified
source change. No performance improvement is claimed by this task: profiling is
complete and optimization is deliberately deferred.
