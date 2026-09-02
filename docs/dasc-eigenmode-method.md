# Causal finite-cavity eigenmode method

This section derives the causal electromagnetic self-field of an axisymmetric
source in a cylindrical perfect-electric-conductor (PEC) cavity. A centered
aperture connects the cavity to a semi-infinite circular pipe. This is a
boundary-aware, time-retarded problem; it is not the free-space Poisson problem
solved by the [TGF method](dasc-tgf-method.md).

1. [Geometry, sources, gauge, and boundaries](dasc-eigenmode-problem.md)
2. [Closed-cavity retarded modal solution](dasc-eigenmode-closed-cavity.md)
3. [Analytical field reconstruction](dasc-eigenmode-fields.md)
4. [Aperture coupling and downstream pipe](dasc-eigenmode-aperture.md)
5. [Verification, convergence, and evidence](dasc-eigenmode-verification.md)

!!! warning "Three distinct physical problems"
    The closed cavity is the exactly derived reference problem. The
    aperture-coupled cavity and pipe require mode matching. Small-aperture
    theory is only a controlled asymptotic benchmark when its scale conditions
    hold; it is not the primary aperture model.

The derivation follows the reviewed DASC
[finite-cavity source](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/space_charge_fields_with_aperture_study.tex).
The earlier small-hole manuscript and incremental supplements are legacy
sources, not the controlling formulation.
