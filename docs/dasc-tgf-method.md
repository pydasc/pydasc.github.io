# Truncated Green's-function method

The TGF section concerns the free-space electrostatic or quasistatic Poisson
problem used by the DA–VGF line of work. It is separate from the causal cavity
eigenmode formulation.

1. [Free-space Poisson problem](dasc-tgf-free-space-poisson.md)
2. [TGF/Vico–Greengard–Ferrando formulation](dasc-tgf-formulation.md)
3. [Field and kick construction](dasc-tgf-field-kick.md)
4. [Verification and convergence](dasc-tgf-verification.md)

!!! warning "Model boundary"
    This method solves an open-boundary electrostatic problem in a declared
    frame. Conducting cavities, causal reflections, and aperture coupling require
    the [eigenmode formulation](dasc-eigenmode-method.md). An FFT does not turn
    one boundary-value problem into the other.

See the public DASC
[DA–TGF source study](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/differentiable_symplectic_space_charge_study.tex)
and the current [PyDASC simulation workflow](pydasc/guides/simulation-workflow.md).

