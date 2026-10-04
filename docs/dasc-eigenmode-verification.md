# Eigenmode verification, convergence, and evidence

This page describes the evidence available at the portal's reviewed source locks. New upstream code, manuscripts and campaigns require a separate reviewed result release before their numerical claims appear here.

## Verification hierarchy

Treat analytic derivation, numerical verification, and physical validation as
separate evidence levels. At minimum, a reproducible study must cover:

| Level | Required checks |
|---|---|
| Dimensions and signs | SI units, signed Q and q, electron field directions, RF/self-field separation |
| Source and gauge | Charge normalization, continuity residual, Lorenz-gauge residual |
| Closed-cavity boundaries | Tangential **E** and normal **B** residuals on every PEC surface |
| Symmetry and regularity | E_r = B_θ = 0 on axis; finite longitudinal field; appropriate azimuthal behavior |
| Causality | Zero response before retarded arrival and correct end-wall reflection arrival |
| Modal/quadrature convergence | Independent radial-mode, axial-mode, source-time, observation-time, and summation studies |
| Reference limits | Early-time semi-infinite cathode-pipe solution, constant-velocity image bunch, and justified static/quasistatic limits |
| Aperture matching | Tangential-field continuity, metallic-annulus residual, reciprocity, propagating/evanescent convergence |
| Energy and radiation | Poynting-flux balance and outgoing-wave condition |
| Geometry limits | Closed-cavity recovery as b → 0 and small-hole comparison only when kb and b/a are small |
| Independent solver | Selected full-wave finite-element or finite-integration comparison |
| Particle/DA coupling | Source-iteration convergence and finite-difference checks of selected source, trajectory, and geometry derivatives |

For a boundary quantity g that should vanish, report a normalized residual such
as

<div id="eq-cavity-boundary-residual" class="dasc-equation" role="group" aria-label="Normalized root mean square boundary condition residual">
<math display="block"><msub><mi>R</mi><mi>g</mi></msub><mo>=</mo><mfrac><msqrt><mrow><msub><mo>∫</mo><mrow><mo>∂</mo><mi>Ω</mi></mrow></msub><msup><mrow><mo>|</mo><mi>g</mi><mo>|</mo></mrow><mn>2</mn></msup><mi>d</mi><mi>S</mi></mrow></msqrt><mrow><msub><mi>g</mi><mtext>scale</mtext></msub><msqrt><msub><mo>∫</mo><mrow><mo>∂</mo><mi>Ω</mi></mrow></msub><mi>d</mi><mi>S</mi></msqrt></mrow></mfrac><mo>.</mo></math>
</div>

The scale, sampled boundary, norm, exclusion of singular source points, and
acceptance threshold must be stated. Causal arrival tests require the geometry,
source history, observation point, and expected light-travel time. Convergence
orders or tolerances require multi-resolution evidence, not one mode count.

## Reproducibility record

Every result must identify the full DASC, PyDASC, and documentation commits;
software environment and precision; a,L,b and material model; source profile,
Q, trajectory, particle loading, seed or quiet start; radial, axial, cavity,
pipe, aperture-basis, propagating, and evanescent mode counts; frequency/time
grids and quadrature; summation and resonance treatment; self-consistency
stopping criteria; observable definitions; independent-solver configuration;
and checksums for raw data, configuration, and figures.

## Current evidence boundary

The reviewed DASC source provides the analytic closed-cavity modal equations and
a staged numerical program. It does not provide an allowlisted, reproducible
benchmark artifact establishing the cavity-aperture implementation, convergence,
full-wave agreement, DA derivatives, self-consistent tracking, or physical
validation. Accordingly, this section reports plans and acceptance categories,
not completed numerical results.

Evidence not released by this portal includes application-level aperture
qualification, resonant and lossy-wall studies, finite-source and nonaxisymmetric
validation, self-consistent electromagnetic integration, and independent
full-wave comparisons. This is a statement about the reviewed public evidence
snapshot, not an inventory of missing features in the latest upstream code.
