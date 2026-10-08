import pytest
from mkdocs.structure.files import File, Files, InclusionLevel
from navigation_policy import validate_navigation


def pages(*names):
    return Files([File(name, "docs", "site", True) for name in names])


def test_unlisted_authored_page_cannot_be_published():
    with pytest.raises(ValueError, match="draft.md"):
        validate_navigation(pages("index.md", "draft.md"), [{"Home": "index.md"}])


def test_excluded_internal_pages_and_assets_need_no_nav_entry():
    files = pages("index.md", "operations/private.md", "assets/logo.png")
    files.get_file_from_path("operations/private.md").inclusion = InclusionLevel.EXCLUDED
    assert validate_navigation(files, [{"Home": "index.md"}]) is files


def test_nested_explicit_navigation_and_approved_imports():
    files = pages("index.md", "pydasc/index.md", "dasc/index.md")
    assert (
        validate_navigation(
            files,
            [
                {"Home": "index.md"},
                {"Projects": [{"P": "pydasc/index.md"}, {"D": "dasc/index.md"}]},
            ],
        )
        is files
    )


def test_missing_explicit_nav_is_rejected():
    with pytest.raises(ValueError, match="explicit navigation"):
        validate_navigation(pages("index.md"), None)
