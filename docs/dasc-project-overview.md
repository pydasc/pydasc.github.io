# DASC project overview

DASC develops the physics description, derivations, analysis methods,
reproducibility rules, and publication evidence for differentiable,
self-consistent space-charge modeling and beam-dynamics maps. Its companion
project, [PyDASC](pydasc/index.md), provides the computational and numerical
software used to implement and test those methods.

!!! important "Scope of this overview"
    This page describes the project architecture and intended evidence flow. It
    does not present a new derivation or promote a planned calculation to a
    validated scientific result. The [reviewed upstream source overview](dasc/index.md)
    remains available with its immutable revision and status.

## Physical problem

Charged-particle beams generate fields that act back on their own particles.
DASC is concerned with models in which a source distribution produces a
space-charge field, that field contributes to particle evolution, and the
changed distribution can require the field to be evaluated again. The project
keeps two physical formulations separate:

- the [truncated Green's-function method](dasc-tgf-method.md) for an
  electrostatic or quasistatic free-space Poisson problem; and
- the [eigenmode method](dasc-eigenmode-method.md) for causal electromagnetic
  fields in a finite conducting cylindrical cavity with aperture and pipe
  coupling.

These formulations have different domains, boundaries, source assumptions, and
validation requirements. They are not interchangeable field solvers.

## Why self-consistency and differentiability both matter

**Self-consistency** concerns the feedback loop between the particle/source
state and its generated field. **Differentiability** concerns how selected
changes in beam, accelerator, trajectory, or geometry parameters propagate
through a stated model to fields, maps, and observables. A differentiable
calculation is not automatically self-consistent, physically correct,
converged, causal, energy-consistent, or symplectic.

[Differential Algebra and finite-order TPSA](dasc-differential-algebra-methods.md)
represent local parameter dependence around an expansion point. Where a
canonical particle map is defined, Lie methods can help construct or analyze
map composition and symplectic structure. Those tools do not replace separate
checks of field equations, boundary conditions, signs, convergence, or
scientific applicability.

## Project and software responsibilities

| Responsibility | DASC | PyDASC |
| --- | --- | --- |
| Physics problem statements and assumptions | Owns and reviews | Implements only an approved model contract |
| Derivations and method comparison | Owns | Supplies numerical operators and diagnostics |
| DA/TPSA and particle-map interpretation | Defines physical meaning and evidence | Implements supported APIs and coefficient propagation |
| Validation and reproducibility plan | Defines claims, references, acceptance criteria, and records | Supplies tests, benchmark tools, and reproducible calculations |
| Production numerical code | Does not duplicate | Owns |
| Papers and research outputs | Organizes as secondary outputs | Provides recorded software inputs |

## Evidence flow

```text
physical question and assumptions
        ↓
source or particle distribution
        ↓
TGF free-space solve  OR  causal cavity eigenmode solve
        ↓
field, force, kick, or particle map defined by that formulation
        ↓
observables and selected DA/TPSA sensitivities
        ↓
independent checks, convergence evidence, and reproducibility record
```

The same sequence in prose is: establish the physical model first, construct
its source, solve the matching field problem, define how the field affects
particles, propagate only supported parameter sensitivities, and test every
claim against independent evidence and convergence criteria.

## Current status and limits

- The portal publishes an approved DASC repository overview, currently labeled
  **Unvalidated** because it describes planned research and future validation.
- PyDASC publishes reviewed software and convention pages through the website's
  explicit source allowlist. Software tests are not by themselves scientific
  validation of every proposed DASC result.
- The detailed DASC physics pages now provide reviewed shared foundations, TGF
  and causal eigenmode derivations, DA/TPSA/Lie methods, a method comparison,
  and a claim-level validation matrix. They do not publish an approved numerical
  result package.
- Planned kinetic-resonance, optimization, aperture-coupling, and
  self-consistent-trajectory results must not be described as completed.
- The two formulations intentionally omit or postpone phenomena outside their
  stated boundaries; those limits will be recorded with each derivation rather
  than inferred here.

## Authoritative records

- [DASC source, issues, and research records](https://github.com/pydasc/dasc)
- [PyDASC source, releases, and issues](https://github.com/pydasc/pydasc)
- [Reviewed DASC source overview](dasc/index.md)
- [Portal collection and publication policy](https://github.com/pydasc/pydasc.github.io)
- [Reproducibility section](dasc-reproducibility.md)
- [Physics claim validation matrix](dasc-validation-matrix.md)
- [Research outputs and publications](dasc-research-outputs.md)
