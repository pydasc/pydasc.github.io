# Physics foundations

This section defines the shared source, field, and particle-dynamics language
used by the TGF and eigenmode formulations. Read the pages in order:

1. [Frames, coordinates, units, and conventions](dasc-conventions.md)
2. [Self-consistent space charge](dasc-self-consistent-space-charge.md)
3. [Potentials, fields, and particle dynamics](dasc-potentials-fields-dynamics.md)
4. [Approximations and validity limits](dasc-validity-limits.md)

The TGF method uses an electrostatic or quasistatic free-space Poisson model.
The eigenmode method uses a causal time-dependent electromagnetic model with
conducting boundaries. Shared notation does not make those models
interchangeable.

Primary candidate sources are the public DASC
[DA–TGF study](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/differentiable_symplectic_space_charge_study.tex)
and [reassessed cavity study](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/space_charge_fields_with_aperture_study.tex).
Linking these sources does not add them to the website publication allowlist.

!!! warning "Scientific status"
    These pages organize derivations traceable to reviewed public sources. They
    do not claim that every proposed solver, coupling, map, or scientific result
    has completed numerical or experimental validation.

