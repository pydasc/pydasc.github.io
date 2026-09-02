# Differential Algebra, TPSA, and Lie methods

Differential Algebra (DA) supplies arithmetic on finite Taylor expansions;
Truncated Power Series Algebra (TPSA) is the finite polynomial representation
used to carry those expansions through a computation. Lie operators describe
canonical transformations when the variables and generator are Hamiltonian.
These tools answer different questions and do not certify the underlying field
model.

1. [DA/TPSA objects and coefficient interpretation](dasc-da-tpsa.md)
2. [Differentiating self-consistent calculations](dasc-da-self-consistency.md)
3. [Lie maps and symplectic structure](dasc-da-lie-maps.md)
4. [Parallel TGF and eigenmode dependency maps](dasc-da-pipelines.md)
5. [Derivative verification, limits, and scaling](dasc-da-verification.md)

!!! warning "Separate properties"
    Differentiability means a local derivative exists and is propagated
    consistently. Energy consistency ties a force to a declared discrete
    energy. Symplecticity is a canonical-map property. Physical correctness,
    convergence, gauge consistency, and causality require their own tests.

The method scope follows the reviewed DASC
[DA–TGF study](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/differentiable_symplectic_space_charge_study.tex)
and [physics-first research plan](https://github.com/chongshikpark/dasc/blob/94033eae4d8eac81f4c42c41f6cfba69e1cd2a25/docs/space_charge_research_plan.tex).
Proposed collective effects and performance claims are not evidence here.
