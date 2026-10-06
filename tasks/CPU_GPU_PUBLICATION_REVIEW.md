# CPU parallel and GPU documentation promotion

Reviewed 7 October 2026. **Pending upstream publication approval.** This is an
internal release proposal outside `docs/`; it is not a published capability or
scientific-result record.

## Reviewed inputs

| Project | Observed committed revision | Relevant changes |
| --- | --- | --- |
| PyDASC | `a7e4596601d62fa838a087e34d0902ed180f20b3` | CPU job/kernel parallelism, automatic CUDA selection, resident and batched numerical paths, bounded GPU-memory measurements, required CUDA CI, platform-aware installation extras |
| DASC | `c933839e10b692077a2988a84833e79e7542c530` | CPU/CUDA campaign execution, resource budgets, exact-source continuation, CPU thread-policy checks and required CUDA integration CI |

Both committed LICENSE files use MIT with attribution to Chong Shik Park,
Ph.D. Licensing permits redistribution, but does not replace the repository's
explicit publication approvals. The DASC worktree has an untracked
`run_all.sh`; it was not read or included in this review.

## Publication blockers

- PyDASC's current contract still selects content commit
  `b5676d387d027958e804af6bebff4862dd4967c1` and only the four original documents.
  Neither `docs/PARALLEL_EXECUTION.md` nor `docs/GPU_EXECUTION.md` is approved.
  Updating only the website checkout lock would not publish the new CPU/GPU
  documentation.
- The current PyDASC tree has moved `docs/SIMULATION_WORKFLOW.md` into
  `tasks/SIMULATION_WORKFLOW.md`. The task copy includes internal campaign
  status and is not a replacement public import. Before promoting a new content
  commit, provide a public workflow guide under `docs/` or explicitly retire
  the old import and update all portal references.
- DASC's current contract has `publication_decision.state: blocked` and an empty
  file list. The source-lock updater rejects these candidate checkouts with
  `DASC publication decision is not approved` and leaves the manifest unchanged.
- The new DASC execution report mixes usage instructions with manuscript/task
  status, hardware measurements and CI administration. Do not import the whole
  report or its supporting JSON, LaTeX, execution plans or campaign artifacts.

## Proposed public update

| Project | Proposed upstream source | Website destination | Required review |
| --- | --- | --- | --- |
| PyDASC | `docs/PARALLEL_EXECUTION.md` | `pydasc/guides/parallel-execution.md` | CPU process/kernel budgets, independent jobs, native TPSA context isolation and memory limitations |
| PyDASC | `docs/GPU_EXECUTION.md` | `pydasc/guides/gpu-execution.md` | CUDA selection, supported kernels, remaining CPU boundaries; separate operational guidance from unapproved performance/result evidence |
| DASC | New public `docs/COMPUTE_EXECUTION.md` | `dasc/guides/compute-execution.md` | Curated campaign runtime guide with explicit resources and reproducibility limits; exclude research results and internal administration |

The PyDASC overview, API policy, conventions and public workflow must also be
reviewed at the new content commit; approval of the two new guides alone does
not approve changed versions of the existing imports. Review the DASC overview
separately before reapproving its existing destination.

The proposed public guidance should cover:

- PyDASC: inspect `current_compute_backend()`; `auto` uses CUDA only after its
  readiness probe, `cpu` forces the reference path, and `cuda` requires CUDA.
  Runtime CUDA failures propagate. CPU process and kernel parallelism are
  opt-in through `use_parallel(workers=..., kernel_workers=...)`. Construct
  solvers inside the selected context. Bound process/thread counts, native
  library threads, per-process RAM and VRAM independently.
- Distinguish independent jobs from dependent time steps and shared
  self-consistent fields. Native TPSA implementations retain CPU boundaries;
  openPMD MPI is parallel I/O, not a distributed solver. Some Gaussian float,
  tangent and controlled tracking paths retain device intermediates, while
  public arrays and other operations still cross host boundaries. Avoid the
  outdated blanket claim that no tracking path is device-resident.
- DASC: distinguish total `--cpus` from `--workers`; CUDA campaigns currently
  require one worker. Record `--backend`, the visible GPU index, host-memory
  budget and GPU pool/reserve budgets. Preserve scientific inputs and recorded
  source revisions when resuming. Use separate CPU/CUDA outputs. Resource
  failures must not silently reduce the scientific problem or switch devices.
- Treat execution parity, hardware capacity, speedup and scientific convergence
  as separate claims. CI configuration alone does not establish a successful
  remote GPU run. Small tests and resource pilots do not qualify production
  particle/grid combinations or complete scientific gates.

## Promotion sequence

1. Obtain authorization to make the necessary upstream documentation and
   publication-contract changes. Website AGENTS.md rule 1 currently makes those
   repositories read-only inputs.
2. Prepare and review only the public source files listed above and the existing
   imports. Commit the public content upstream, then commit contracts pointing
   to those exact content SHAs with approved paths, status, license and DASC
   attribution/publication evidence. Keep development notes and results excluded.
3. Make those commits available to the production source fetch. The website must
   not use temporary local-only commits as production locks.
4. Update the website manifest to the reviewed contract commits and explicit
   paths; add navigation and links from project selection and reproducibility.
   Regenerate imports through the collector.
5. Run tests, deterministic assembly, document/physics validation, strict build,
   site-link/accessibility checks and the complete artifact scan. Review the
   publication diff before deployment.

The production manifest and navigation remain at the previously approved
release while this proposal is pending. No upstream code was executed and no
upstream files, contracts, commits or remote state were changed.

## Verification of the existing approved release

On 7 October 2026, isolated local clones at the existing website locks passed
collection without modifying either upstream worktree. The full pytest suite
passed **268 tests**, with **9 case-insensitive-filesystem cases skipped** on
this Linux filesystem. Tests ran outside the sandbox to allow their temporary
Unix-socket fixtures.

Repeated collection produced identical generated files and inventory. Document
and physics validation, strict MkDocs build, site links, accessibility and the
complete artifact scan passed. The internal proposal is absent from the built
site. These checks verify the existing approved snapshot, not approval or
validation of the proposed new imports. Candidate source-lock promotion was
separately rejected by the DASC publication gate as described above.
