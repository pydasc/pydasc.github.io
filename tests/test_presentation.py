from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import sys

from validate_accessibility import validate as validate_accessibility
from validate_site import validate as validate_site
from mkdocs_hooks import on_page_content


ROOT = Path(__file__).parents[1]
CSS = ROOT / "docs/stylesheets/readthedocs.css"


@pytest.mark.parametrize(
    "html",
    [
        '<a href="javascript:alert(1)" href="https://example.com/">Link</a>',
        '<a href="https://example.com/" HREF="javascript:alert(1)">Link</a>',
        '<img src="data:text/html,active" SRC="approved.png" />',
        '<a href="https://example.com/" href="https://example.com/">Link</a>',
    ],
)
def test_site_validation_rejects_duplicate_attributes(tmp_path: Path, html: str) -> None:
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate HTML attribute"):
        validate_site(tmp_path, CSS)


def test_readthedocs_stylesheet_and_local_assets_are_configured() -> None:
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))

    assert config["extra_css"] == ["stylesheets/readthedocs.css"]
    assert config["extra_javascript"] == ["javascripts/navigation.js"]
    assert config["theme"]["font"] is False
    assert "navigation.path" in config["theme"]["features"]
    assert "navigation.footer" in config["theme"]["features"]
    assert "navigation.tabs" not in config["theme"]["features"]
    assert "overrides/" in config["exclude_docs"].splitlines()
    assert "TODO.md" in config["exclude_docs"].splitlines()
    assert "CODEX_TASKS_DASC_PHYSICS_DOCUMENTATION.md" in config["exclude_docs"].splitlines()
    assert "browser_control.md" in config["exclude_docs"].splitlines()
    footer = (ROOT / "docs/overrides/partials/footer.html").read_text(encoding="utf-8")
    assert "project_group(current_url)" in footer
    assert "previous_group == current_group" in footer
    assert "next_group == current_group" in footer


def test_required_tokens_desktop_sidebar_and_bounded_content_exist() -> None:
    css = CSS.read_text(encoding="utf-8")
    required = {
        "--dasc-sidebar-width": "300px",
        "--dasc-sidebar-bg": "#343131",
        "--dasc-sidebar-muted": "#9b9b9b",
        "--dasc-accent": "#2980b9",
        "--dasc-page-bg": "#fcfcfc",
        "--dasc-text": "#404040",
        "--dasc-content-max": "1000px",
    }
    for token, value in required.items():
        assert re.search(rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;", css)

    assert "@media screen and (min-width: 76.25em)" in css
    assert "width: var(--dasc-sidebar-width)" in css
    assert "max-width: var(--dasc-content-max)" in css
    assert ".md-sidebar--secondary:not([hidden])" in css
    assert re.search(r"\.md-sidebar--secondary:not\(\[hidden\]\)\s*\{\s*display:\s*none;\s*\}", css)
    assert ".md-sidebar--secondary:not([hidden]) ~ .md-content > .md-content__inner" in css
    assert re.search(r"\.md-content\s*\{\s*max-width:\s*none;", css)


def test_mobile_accessibility_overflow_motion_and_print_rules_exist() -> None:
    css = CSS.read_text(encoding="utf-8")
    header = (ROOT / "docs/overrides/partials/header.html").read_text(encoding="utf-8")
    javascript = (ROOT / "docs/javascripts/navigation.js").read_text(encoding="utf-8")

    assert "@media screen and (max-width: 76.234375em)" in css
    assert "overflow-x: hidden" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "@media print" in css
    assert "size: landscape" in css
    assert ".dasc-table-scroll:focus-visible" in css
    assert "overflow-x: auto" in css
    assert "overscroll-behavior-inline: contain" in css
    assert ".dasc-table-scroll > table:not([class])," in css
    assert ".dasc-table-scroll table:not([class])" in css
    assert re.search(
        r"\.dasc-table-scroll\s+:is\(\.md-typeset__scrollwrap,\s*"
        r"\.md-typeset__table\)\s*\{[^}]*"
        r"width:\s*max-content;[^}]*overflow:\s*visible;",
        css,
        re.DOTALL,
    )
    assert re.search(
        r"@media print\s*\{.*\.dasc-table-scroll table:not\(\[class\]\)"
        r"\s*\{[^}]*width:\s*100%;[^}]*table-layout:\s*fixed;",
        css,
        re.DOTALL,
    )
    assert "counter-increment: dasc-equation" in css
    assert 'content: "(" counter(dasc-equation) ")"' in css
    assert 'aria-controls="__drawer"' in header
    assert 'aria-label="Open documentation navigation"' in header
    content = (ROOT / "docs/overrides/partials/content.html").read_text(encoding="utf-8")
    assert 'aria-label="Breadcrumb"' in content
    assert 'aria-current="page"' in content
    assert 'event.key === "Enter"' in javascript
    assert 'event.key === "Escape"' in javascript
    assert not re.search(r"url\(\s*['\"]?/", css)
    assert "/Users/" not in css + header + javascript


def test_built_site_passes_semantic_accessibility_audit(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<!doctype html><html lang="en"><head><title>Page</title></head>'
        '<body><nav aria-label="Primary"></nav><main><h1>Page</h1>'
        '<h2>Section</h2><div class="dasc-table-scroll" role="region" '
        'tabindex="0" aria-label="Scrollable table: Values">'
        "<table><tr><th>Value</th></tr></table></div>"
        '<img src="example.png" alt="Example"></main></body></html>',
        encoding="utf-8",
    )
    validate_accessibility(tmp_path)


def test_table_hook_adds_named_keyboard_scroll_regions() -> None:
    class Page:
        title = 'Methods & "evidence"'

    rendered = on_page_content(
        "<h1>Page</h1><table><thead><tr><th>Value</th></tr></thead></table>",
        Page(),
    )

    assert rendered.count('class="dasc-table-scroll"') == 1
    assert 'role="region"' in rendered
    assert 'tabindex="0"' in rendered
    assert 'aria-label="Scrollable table: Methods &amp; &quot;evidence&quot;, table 1"' in rendered
    assert "<table><thead>" in rendered


def test_accessibility_audit_rejects_unwrapped_table(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<!doctype html><html lang="en"><head><title>Page</title></head>'
        '<body><nav aria-label="Primary"></nav><main><h1>Page</h1>'
        "<table><tr><th>Value</th></tr></table></main></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lack keyboard-scrollable regions"):
        validate_accessibility(tmp_path)


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,active", "file:///tmp/private"]
)
def test_site_validation_rejects_unsafe_url_schemes(tmp_path: Path, url: str) -> None:
    (tmp_path / "index.html").write_text(
        f'<html><body><a href="{url}">unsafe</a></body></html>',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsafe URL scheme"):
        validate_site(tmp_path, CSS)


def test_site_validation_resolves_root_relative_links_from_site_root(tmp_path: Path) -> None:
    nested = tmp_path / "guide"
    nested.mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/main.css").write_text("body {}", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<html><head><link href="stylesheets/readthedocs.css"></head><body>'
        '<button data-dasc-drawer-control aria-controls="__drawer" '
        'aria-label="Open documentation navigation"></button>'
        '<a href="guide/">Guide</a></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "stylesheets").mkdir()
    (tmp_path / "stylesheets/readthedocs.css").write_text("", encoding="utf-8")
    (nested / "index.html").write_text(
        '<html><head><link href="/assets/main.css"></head><body></body></html>',
        encoding="utf-8",
    )

    validate_site(tmp_path, CSS)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", "portal"),
        ("pydasc/", "pydasc"),
        ("pydasc/reference/conventions/", "pydasc"),
        ("pydasc-other/", "portal"),
        ("dasc/", "dasc"),
        ("dasc-tgf-method/", "dasc"),
    ],
)
def test_footer_project_group_boundaries(url, expected):
    from jinja2 import Environment

    source = (ROOT / "docs/overrides/partials/footer.html").read_text()
    # Extract the actual macro; the rest of the template needs page/theme context.
    macro = source[: source.index("{%- endmacro %}") + len("{%- endmacro %}")]
    assert Environment().from_string(macro).module.project_group(url) == expected


@pytest.mark.parametrize(
    ("current", "neighbor", "visible"),
    [
        ("pydasc/", "pydasc/reference/conventions/", True),
        ("pydasc/reference/conventions/", "pydasc/", True),
        ("pydasc/reference/conventions/", "contributing/", False),
        ("dasc-tgf-method/", "dasc/", True),
        ("dasc/", "pydasc/", False),
    ],
)
def test_footer_renders_only_same_project_neighbors(current, neighbor, visible):
    from jinja2 import DictLoader, Environment
    from types import SimpleNamespace

    source = (ROOT / "docs/overrides/partials/footer.html").read_text()
    env = Environment(
        loader=DictLoader(
            {
                "footer": source,
                ".icons/material/arrow-left.svg": "",
                ".icons/material/arrow-right.svg": "",
                "partials/copyright.html": "",
            }
        )
    )
    env.filters["url"] = lambda url: url
    other = SimpleNamespace(url=neighbor, title="Neighbor")
    html = env.get_template("footer").render(
        page=SimpleNamespace(url=current, previous_page=other, next_page=other),
        features=["navigation.footer"],
        lang=SimpleNamespace(t=lambda s: s),
        config={"theme": {"icon": {}}, "extra": {}},
    )
    assert (f'href="{neighbor}"' in html) is visible


@pytest.mark.parametrize(
    "content",
    [
        '<nav aria-label="Main"></nav><nav></nav>',
        '<nav aria-labelledby="missing"></nav>',
        '<span id="name"> </span><nav aria-labelledby="name"></nav>',
        '<nav aria-label=" "></nav>',
        '<nav aria-label="Main" ARIA-LABEL="Other"></nav>',
        '<nav aria-label="Main"></nav><div class="dasc-table-scroll" role="region" tabindex="0" aria-label="Tables"><table><tr><th>A</th></tr></table><table><tr><td>B</td></tr></table></div>',
        '<nav aria-label="Main"></nav><div class="dasc-table-scroll" role="region" tabindex="0" aria-label="Tables"><table><tr><td><table><tr><th>Nested</th></tr></table></td></tr></table></div>',
    ],
)
def test_accessibility_checks_each_element(tmp_path, content):
    (tmp_path / "index.html").write_text(
        '<html lang="en"><head><title>Page</title></head><body>'
        "<main><h1>Page</h1>" + content + "</main></body></html>"
    )
    with pytest.raises(ValueError):
        validate_accessibility(tmp_path)


def test_accessibility_resolves_forward_labels_and_nested_text(tmp_path):
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>Page</title><body><main><h1>Page</h1>'
        '<nav aria-labelledby="label"></nav><nav aria-label="Other"></nav>'
        '<span id="label">Named <b>navigation</b></span></main></body></html>'
    )
    validate_accessibility(tmp_path)


def test_accessibility_rejects_empty_title(tmp_path):
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title> </title><main><h1>Page</h1>'
        '<nav aria-label="Main"></nav></main></html>'
    )
    with pytest.raises(ValueError, match="empty title"):
        validate_accessibility(tmp_path)


def test_material_navigation_uses_text_bearing_label():
    from jinja2 import DictLoader, Environment
    from mkdocs_hooks import on_env

    source = '<nav aria-labelledby="{{ path }}_label"><label class="md-nav__title" for="{{ path }}">Project</label></nav>'
    env = Environment(loader=DictLoader({"partials/nav-item.html": source}))
    on_env(env)
    on_env(env)
    rendered = env.get_template("partials/nav-item.html").render(path="section")
    assert 'aria-labelledby="section_title"' in rendered
    assert 'id="section_title">Project' in rendered
    with pytest.raises(ValueError, match="template changed"):
        on_env(Environment(loader=DictLoader({"partials/nav-item.html": "changed theme"})))


@pytest.mark.parametrize("reference", ["#missing", "other/#missing", "other/#%6dissing"])
def test_document_index_rejects_missing_fragments(tmp_path, reference):
    from html_references import DocumentIndex

    (tmp_path / "index.html").write_text('<h1 id="home">Home</h1>')
    (tmp_path / "other").mkdir()
    (tmp_path / "other/index.html").write_text('<h1 id="target">Other</h1>')
    with pytest.raises(ValueError, match="undefined local fragment"):
        DocumentIndex(tmp_path).validate(tmp_path / "index.html", reference)


def test_document_index_resolves_fragments_base_and_queries(tmp_path):
    from html_references import DocumentIndex

    page = tmp_path / "index.html"
    page.write_text('<h1 id="target">Home</h1><a name="legacy"></a>')
    index = DocumentIndex(tmp_path, "/preview/")
    for raw in ["#target", "?q=value#target", "/preview/#%74arget", "#legacy", "#"]:
        index.validate(page, raw)
    with pytest.raises(ValueError, match="outside the configured site base"):
        index.validate(page, "/elsewhere/#target")
