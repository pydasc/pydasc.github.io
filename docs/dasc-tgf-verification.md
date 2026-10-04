# TGF verification and convergence

This page describes the evidence available at the portal's reviewed source locks. New upstream code, manuscripts and campaigns require a separate reviewed result release before their numerical claims appear here.

## Verification plan

Verification must distinguish the continuous free-space model, its discrete
convolution, the deposition model, and the particle kick. A passing software
test is necessary evidence about implementation behavior, not sufficient
evidence of physical accuracy.

For a sampled reference field f_ref and numerical field f_h, report the relative
discrete L² error

<div id="eq-tgf-relative-l2" class="dasc-equation" role="group" aria-label="Relative discrete L2 error">
<math display="block"><msub><mi>e</mi><mn>2</mn></msub><mo>=</mo><mfrac><msqrt><mrow><mi>Δ</mi><mi>V</mi><munderover><mo>∑</mo><mi>g</mi><mi>N</mi></munderover><msup><mrow><mo>|</mo><msub><mi>f</mi><mi>h</mi></msub><mo>(</mo><msub><mi mathvariant="bold">x</mi><mi>g</mi></msub><mo>)</mo><mo>−</mo><msub><mi>f</mi><mtext>ref</mtext></msub><mo>(</mo><msub><mi mathvariant="bold">x</mi><mi>g</mi></msub><mo>)</mo><mo>|</mo></mrow><mn>2</mn></msup></mrow></msqrt><mrow><msqrt><mrow><mi>Δ</mi><mi>V</mi><munderover><mo>∑</mo><mi>g</mi><mi>N</mi></munderover><msup><mrow><mo>|</mo><msub><mi>f</mi><mtext>ref</mtext></msub><mo>(</mo><msub><mi mathvariant="bold">x</mi><mi>g</mi></msub><mo>)</mo><mo>|</mo></mrow><mn>2</mn></msup></mrow></msqrt></mrow></mfrac><mo>.</mo></math>
</div>

Use a smooth three-dimensional Gaussian with analytic free-space potential and
field as the primary reference. Run the following controls independently:

| Question | Required comparison |
|---|---|
| Potential and field accuracy | L² and maximum-norm errors against the analytic solution |
| Grid convergence | Refine equal-spacing grids at fixed physical domain and cutoff policy |
| Domain convergence | Enlarge the physical box at fixed resolved source scale |
| Cutoff and padding | Vary admissible cutoff and padding; reject inadmissible geometry |
| Normalization and sign | Integrate deposited charge and check potential/field sign and 1/ε₀ scaling |
| Deposition convergence | Vary particle count, shape, and source resolution separately from grid refinement |
| Energy-force consistency | Compare [the analytic discrete gradient](dasc-tgf-field-kick.md#eq-tgf-energy-force) with centered finite differences of U_h |
| Operator symmetry | Test the discrete bilinear reciprocity relation for K_h |
| Self-force and momentum balance | Test isolated-particle self-force and total internal-force cancellation for symmetric configurations |
| Map structure | Measure reversibility and the canonical symplectic defect of the composed tracking map |

Do not infer a convergence order until at least three asymptotic resolutions
show a stable slope, and do not vary grid, domain, particle count, and shape in
the same sequence. Near-zero reference norms require an absolute-error report
instead of [the relative metric](#eq-tgf-relative-l2).

## Reproducibility record

Each published run must retain:

| Category | Required values |
|---|---|
| Source identity | Full PyDASC, DASC, and documentation commit SHAs |
| Runtime | Python and dependency lock, platform, backend, floating-point precision |
| Mesh and geometry | Axis order, grid shape, physical bounds, spacing, padding, cutoff radius |
| Source | Distribution parameters, total charge, particle count, deposition shape and parameters |
| Tracking | Time step, number of steps, frame, canonical coordinates, external-map splitting |
| Randomness | Generator and seed, or an explicit deterministic-data statement |
| Outputs | Norm definitions, raw-data location, configuration, and checksums |

## Current evidence boundary

The reviewed PyDASC source contains unit tests and benchmark entry points for
the free-space solver and discrete Hamiltonian. This portal does not currently
publish an approved benchmark data set or a release result table, so it makes no
numerical accuracy, convergence-order, performance, reversibility, or
symplectic-defect claim. Results belong here only after their exact configuration,
raw artifacts, acceptance thresholds, and source commits have been reviewed.

Open verification items include anisotropic domains that fail the twofold
cutoff interval, boundary and self-force behavior for each deposition model,
particle-number convergence, and the canonical normalization of a complete
DASC tracking composition.
