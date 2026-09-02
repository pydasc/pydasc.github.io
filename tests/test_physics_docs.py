from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_physics_docs import MISPLACED_MEASURE_EXPONENT, validate


def test_authored_physics_docs_have_valid_equations_and_citations() -> None:
    validate(ROOT / "docs")


def test_undefined_equation_and_citation_keys_fail(tmp_path: Path) -> None:
    page = tmp_path / "dasc-test.md"
    page.write_text("# Test\n\n[missing](#eq-missing) and citation[^missing].\n")
    with pytest.raises(ValueError):
        validate(tmp_path)


def test_measure_exponent_on_coordinate_fails(tmp_path: Path) -> None:
    page = tmp_path / "dasc-test.md"
    page.write_text(
        '# Test\n\n<div id="eq-test" class="dasc-equation" role="group" '
        'aria-label="Invalid measure">\n<math display="block">'
        '<mi>d</mi><msup><mi>r</mi><mn>3</mn></msup></math>\n</div>\n'
    )
    with pytest.raises(ValueError, match="measure exponent"):
        validate(tmp_path)


def test_three_dimensional_measures_use_d_cubed_not_coordinate_cubed() -> None:
    physics = "\n".join(
        page.read_text() for page in sorted((ROOT / "docs").glob("dasc-*.md"))
    )
    assert "<mrow><mi>d</mi><mi>V</mi></mrow>" in physics
    assert '<mrow><msup><mi>d</mi><mn>3</mn></msup><mi mathvariant="bold">r</mi></mrow>' in physics
    assert '<mrow><msup><mi>d</mi><mn>3</mn></msup><mi mathvariant="bold">k</mi></mrow>' in physics
    assert not MISPLACED_MEASURE_EXPONENT.search(physics)


def test_fixed_point_notation_is_not_parsed_as_markdown_emphasis() -> None:
    source = (ROOT / "docs/dasc-da-self-consistency.md").read_text()
    rendered = markdown.markdown(source, extensions=["md_in_html"])

    assert "x*(θ)" not in source
    assert "x<em>(θ) satisfies x</em>" not in rendered
    assert "</p>\n<math><msup><mi>x</mi>" not in rendered
    assert "<math><msup><mi>x</mi><mo><em>" not in rendered
    assert rendered.count("<msup><mi>x</mi><mo>∗</mo></msup>") == 3


def test_tgf_derivation_is_explicitly_navigated() -> None:
    config = (ROOT / "mkdocs.yml").read_text()
    for page in (
        "dasc-tgf-free-space-poisson.md",
        "dasc-tgf-formulation.md",
        "dasc-tgf-field-kick.md",
        "dasc-tgf-verification.md",
    ):
        assert page in config

    equations = "\n".join(
        (ROOT / "docs" / page).read_text()
        for page in (
            "dasc-tgf-free-space-poisson.md",
            "dasc-tgf-formulation.md",
            "dasc-tgf-field-kick.md",
            "dasc-tgf-verification.md",
        )
    )
    for equation_id in (
        "eq-tgf-poisson",
        "eq-tgf-green-convolution",
        "eq-tgf-cutoff-condition",
        "eq-tgf-spectrum",
        "eq-tgf-direct-field",
        "eq-tgf-discrete-energy",
        "eq-tgf-energy-force",
        "eq-tgf-kick",
        "eq-tgf-relative-l2",
    ):
        assert f'id="{equation_id}"' in equations


def test_eigenmode_derivation_is_explicitly_navigated() -> None:
    pages = (
        "dasc-eigenmode-problem.md",
        "dasc-eigenmode-closed-cavity.md",
        "dasc-eigenmode-fields.md",
        "dasc-eigenmode-aperture.md",
        "dasc-eigenmode-verification.md",
    )
    config = (ROOT / "mkdocs.yml").read_text()
    assert all(page in config for page in pages)

    equations = "\n".join((ROOT / "docs" / page).read_text() for page in pages)
    for equation_id in (
        "eq-cavity-domains",
        "eq-cavity-source",
        "eq-cavity-wave-equations",
        "eq-cavity-potential-boundaries",
        "eq-cavity-radial-mode",
        "eq-cavity-scalar-green",
        "eq-cavity-scalar-potential",
        "eq-cavity-fields",
        "eq-cavity-lorentz-force",
        "eq-aperture-matching",
        "eq-small-aperture-limit",
        "eq-cavity-boundary-residual",
    ):
        assert f'id="{equation_id}"' in equations


def test_da_tpsa_lie_section_is_explicitly_navigated() -> None:
    pages = (
        "dasc-da-tpsa.md",
        "dasc-da-self-consistency.md",
        "dasc-da-lie-maps.md",
        "dasc-da-pipelines.md",
        "dasc-da-verification.md",
    )
    config = (ROOT / "mkdocs.yml").read_text()
    assert all(page in config for page in pages)

    equations = "\n".join((ROOT / "docs" / page).read_text() for page in pages)
    for equation_id in (
        "eq-tpsa-expansion",
        "eq-tpsa-coefficient-derivative",
        "eq-tpsa-small-example",
        "eq-da-linear-field-propagation",
        "eq-da-fixed-point-derivative",
        "eq-da-poisson-bracket",
        "eq-da-symmetric-split",
        "eq-da-symplectic-defect",
        "eq-da-derivative-error",
    ):
        assert f'id="{equation_id}"' in equations


def test_comparison_validation_and_reproducibility_are_navigated() -> None:
    config = (ROOT / "mkdocs.yml").read_text()
    for page in (
        "dasc-method-selection.md",
        "dasc-validation-matrix.md",
        "dasc-reproducibility.md",
    ):
        assert page in config

    matrix = (ROOT / "docs/dasc-validation-matrix.md").read_text()
    assert "Artifact pending" in matrix
    assert "Cavity calculation is self-consistent and symplectic" in matrix
    assert "**Open.** No current claim is allowed." in matrix

    reproducibility = (ROOT / "docs/dasc-reproducibility.md").read_text()
    for required in (
        "Full DASC, PyDASC, website",
        "seed or quiet-start definition",
        "SHA-256 checksums",
        "known limitations",
    ):
        assert required in reproducibility


def test_validation_matrix_evidence_links_are_complete_and_immutable() -> None:
    matrix = (ROOT / "docs/dasc-validation-matrix.md").read_text()
    sha = "0506b8a9feb75813ae979f0c1c25a307b21096d2"
    urls = re.findall(
        r"https://github\.com/chongshikpark/pydasc/(?:blob|tree)/"
        + sha
        + r"/[^)]+",
        matrix,
    )

    assert len(urls) >= 35
    assert "/main/" not in matrix
    assert "/master/" not in matrix
    for path in re.findall(r"`([^`]+\.py)`", matrix):
        expected = (
            f"[`{path}`](https://github.com/chongshikpark/pydasc/blob/{sha}/{path})"
        )
        assert expected in matrix


def test_reader_facing_physics_pages_do_not_reference_completed_tasks() -> None:
    task_reference = re.compile(r"\b(?:future |later |subsequent )?tasks?\s+\d+\b", re.I)

    for page in (ROOT / "docs").glob("dasc-*.md"):
        assert not task_reference.search(page.read_text()), page
