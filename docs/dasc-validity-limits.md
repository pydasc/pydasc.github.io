# Approximations and validity limits

## Exact identities

Within a declared frame and smoothness class, charge conservation, the Lorenz-
gauge potential equations, field definitions, and Lorentz force are continuum
identities. They do not specify a boundary model, numerical discretization, or
particle integrator.

## Modeling approximations

| Choice | What it permits | What it omits or postpones |
| --- | --- | --- |
| Electrostatic/quasistatic TGF solve | Free-space Poisson field evaluation in a declared frame | Retardation and conducting-boundary response in that solve |
| Axisymmetric cavity source | Radial/axial modal reduction | Non-axisymmetric source and field modes |
| Prescribed z_b(t) baseline | Causal field evaluation for a known source history | Feedback of the computed self-field on that same trajectory |
| Perfect electric conductors | Ideal cavity/pipe boundary conditions | Finite conductivity, dispersion, roughness, and loss unless added explicitly |
| Thin or zero-length bunch slice | Focused analytical source model | Finite longitudinal profile unless generalized and revalidated |
| Local DA/TPSA expansion | Parameter sensitivities inside a trust region | Branch changes, global guarantees, and physics validation |

## Discretizations and implementation choices

Grid spacing, finite domain, padding, particle shape, mode count, quadrature,
time step, split order, and floating-point precision are numerical choices—not
new physical laws. Each requires refinement or independent comparison. An FFT
or modal sum can converge to the wrong problem if its signs, normalization,
boundaries, or source model are wrong.

## Regularity, causality, and conservation

- TGF spectral convergence statements require the source regularity and support
  assumed by the underlying method; particle noise or nonsmooth deposition can
  change observed convergence.
- Cavity fields must have retarded support. Results before causal arrival, or
  after a reflected signal is omitted, indicate a different model or an error.
- Charge normalization must survive source construction. Energy, momentum, and
  symplectic checks apply only to the map and discrete Hamiltonian for which
  they are derived.
- A converged potential does not prove a converged particle force, derivative,
  trajectory, or observable.

## Intentionally unresolved

!!! warning "Boundaries of the reviewed documentation snapshot"
    This public snapshot does not establish a common metric/frame convention,
    TGF canonical normalization, self-consistent cavity trajectory closure,
    finite-bunch qualification or a universally valid differentiated parameter
    set. Current upstream implementations may go beyond this snapshot; their
    presence alone does not release or qualify new public claims. State the
    convention, source history, parameter set and validation range for each
    formulation before extending these pages.

## Evidence labels

Use **analytic derivation** for a checked consequence of stated assumptions,
**numerical verification** for agreement with equations or an independent
calculation, and **physical validation** only for evidence that the model
describes its intended physical system within stated uncertainty. Passing a
strict documentation build or software unit test is not physical validation.

See [method selection](dasc-method-selection.md) and
[reproducibility](dasc-reproducibility.md) before interpreting a planned result.

