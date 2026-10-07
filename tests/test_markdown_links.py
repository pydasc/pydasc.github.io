"""Markdown links, images and rendered HTML at the publication boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import collect_docs
from collect_docs import MARKDOWN_POLICY_EXTENSIONS, CollectionError, assemble
from validate_docs import validate

from .publication_support import fixture, git


def test_broken_link_and_credential_rejected(tmp_path):
    for text, pattern in (
        ("[bad](missing.md)\n", "broken"),
        ("github_pat_secret\n", "credential"),
    ):
        root = tmp_path / pattern
        root.mkdir()
        m, p, d = fixture(root, ptext=text)
        with pytest.raises(CollectionError, match=pattern):
            assemble(m, root / "out", p, d)


def test_relative_links_relocate_or_use_exact_immutable_source_revision(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text(
        "# P\n\n[Guide](guide.md?view=full#intro)\n[Notes](notes.md?raw=1#top)\n"
    )
    (p / "guide.md").write_text("# Guide\n")
    (p / "notes.md").write_text("# Notes\n")
    git(p, "add", "README.md", "guide.md", "notes.md")
    git(p, "commit", "-qm", "linked content")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract["files"].append(
        {
            "source": "guide.md",
            "destination": "pydasc/guides/guide.md",
            "media_type": "text/markdown",
            "documentation_status": {"label": "Reviewed", "evidence": "test"},
            "redistribution": {"spdx_license": "MIT", "license_file": "LICENSE"},
        }
    )
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve linked content")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["files"].append(
        {"source": "guide.md", "destination": "pydasc/guides/guide.md"}
    )
    m.write_text(yaml.safe_dump(data))
    out = tmp_path / "out"
    assemble(m, out, p, d)
    generated = (out / "pydasc/index.md").read_text()
    assert "[Guide](guides/guide.md?view=full#intro)" in generated
    assert (
        f"[Notes](https://github.com/pydasc/pydasc/blob/{content}/notes.md?raw=1#top)"
        in generated
    )


def test_rewritten_links_url_encode_decoded_path_characters(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text(
        "# P\n\n[Selected](selected%20%28한글%29%23.md#section)\n[Other](other%20%28한글%29%23%3F.md?raw=1#top)\n"
    )
    selected = p / "selected (한글)#.md"
    other = p / "other (한글)#?.md"
    selected.write_text("# Selected\n")
    other.write_text("# Other\n")
    git(p, "add", "README.md", selected.name, other.name)
    git(p, "commit", "-qm", "encoded link targets")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract["files"].append(
        {
            "source": selected.name,
            "destination": "pydasc/guides/selected (한글)#.md",
            "media_type": "text/markdown",
            "documentation_status": {"label": "Reviewed", "evidence": "test"},
            "redistribution": {"spdx_license": "MIT", "license_file": "LICENSE"},
        }
    )
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve encoded link target")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["files"].append(
        {"source": selected.name, "destination": "pydasc/guides/selected (한글)#.md"}
    )
    m.write_text(yaml.safe_dump(data))
    out = tmp_path / "out"
    assemble(m, out, p, d)
    generated = (out / "pydasc/index.md").read_text()
    assert (
        "[Selected](guides/selected%20%28%ED%95%9C%EA%B8%80%29%23.md#section)"
        in generated
    )
    assert (
        f"[Other](https://github.com/pydasc/pydasc/blob/{content}/other%20%28%ED%95%9C%EA%B8%80%29%23%3F.md?raw=1#top)"
        in generated
    )
    selected_page = (out / "pydasc/guides/selected (한글)#.md").read_text()
    encoded_source = "selected%20%28%ED%95%9C%EA%B8%80%29%23.md"
    source_url = f"https://github.com/pydasc/pydasc/blob/{content}/{encoded_source}"
    assert f"source={source_url};" in selected_page
    assert f"]({source_url})" in selected_page
    validate(m, out)


def test_query_only_link_retains_current_page_semantics(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\n[View](?plain=1#details)\n")
    out = tmp_path / "out"
    assemble(m, out, p, d)
    assert "[View](?plain=1#details)" in (out / "pydasc/index.md").read_text()
    validate(m, out)


def test_empty_link_retains_current_page_semantics(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\n[Current page]()\n")
    out = tmp_path / "out"
    assemble(m, out, p, d)
    assert "[Current page]()" in (out / "pydasc/index.md").read_text()
    validate(m, out)


@pytest.mark.parametrize(
    "target",
    [
        "bad%00.md",
        "bad%0A.md",
        "bad%7F.md",
        "bad%5Cname.md",
        "bad%FF.md",
        "bad%ZZ.md",
        "bad%.md",
    ],
)
def test_encoded_unsafe_or_invalid_link_paths_fail_cleanly(tmp_path, target):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n[Bad]({target})\n")
    with pytest.raises(CollectionError, match="link path"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "target", ["//[invalid", "https://[invalid", "//example.com:bad]"]
)
def test_malformed_link_authorities_fail_cleanly(tmp_path, target):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n[Bad]({target})\n")
    with pytest.raises(CollectionError, match="invalid link URL"):
        assemble(m, tmp_path / "out", p, d)


def test_link_like_text_in_code_or_escapes_is_not_rewritten(tmp_path):
    text = "# P\n\n`[inline](missing.md)`\n\n``[long inline](missing.md)``\n\n```text\n```not a closing fence\n[fenced](missing.md)\n```\n\n    [indented](missing.md)\n\n\\[escaped](missing.md)\n"
    m, p, d = fixture(tmp_path, ptext=text)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    generated = (out / "pydasc/index.md").read_text()
    for sample in (
        "[inline](missing.md)",
        "[long inline](missing.md)",
        "[fenced](missing.md)",
        "[indented](missing.md)",
        r"\[escaped](missing.md)",
    ):
        assert sample in generated
    validate(m, out)


@pytest.mark.parametrize("target", ["<guide file.md>", "<guide.md>"])
def test_angle_bracket_link_destinations_are_rejected(tmp_path, target):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n[Guide]({target})\n")
    with pytest.raises(CollectionError, match="angle-bracket link destinations"):
        assemble(m, tmp_path / "out", p, d)


def test_nested_labels_and_balanced_destination_parentheses_are_rewritten(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text(
        '# P\n\n[Nested [label]](guide(section).md "Guide title")\n'
    )
    (p / "guide(section).md").write_text("# Guide\n")
    git(p, "add", "README.md", "guide(section).md")
    git(p, "commit", "-qm", "balanced link syntax")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve balanced link revision")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    out = tmp_path / "out"
    assemble(m, out, p, d)
    generated = (out / "pydasc/index.md").read_text()
    assert (
        f'[Nested [label]](https://github.com/pydasc/pydasc/blob/{content}/guide%28section%29.md "Guide title")'
        in generated
    )


def test_reference_definition_inside_code_is_ignored(tmp_path):
    text = "# P\n\n```markdown\n[guide]: missing.md\n```\n\n    [other]: missing.md\n\n\t[tabbed]: missing.md\n"
    m, p, d = fixture(tmp_path, ptext=text)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    validate(m, out)


@pytest.mark.parametrize("fence", ["```", "~~~"])
@pytest.mark.parametrize("prefix", ["> ", "> > "])
def test_reference_definition_inside_nested_superfence_is_ignored(
    tmp_path, fence, prefix
):
    text = f"# P\n\n{prefix}{fence}markdown\n{prefix}[guide]: missing.md\n{prefix}[example](missing.md)\n{prefix}![image](missing.png)\n{prefix}{fence}\n{prefix.rstrip()}\n{prefix}[Guide][guide]\n"
    m, p, d = fixture(tmp_path, ptext=text)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    validate(m, out)


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_list_fence_like_syntax_follows_configured_renderer(tmp_path, fence):
    text = f"# P\n\n- {fence}markdown\n  [example](missing.md)\n  ![image](missing.png)\n  {fence}\n"
    m, p, d = fixture(tmp_path, ptext=text)
    if fence == "```":
        out = tmp_path / "out"
        assemble(m, out, p, d)
        validate(m, out)
    else:
        with pytest.raises(CollectionError, match="broken or unsafe relative link"):
            assemble(m, tmp_path / "out", p, d)


def test_renderer_prevents_false_fence_mask_from_hiding_active_link(tmp_path):
    text = "# P\n\n> - ~~~markdown\n>   [active](missing.md)\n>   ~~~\n"
    m, p, d = fixture(tmp_path, ptext=text)
    with pytest.raises(CollectionError, match="broken or unsafe relative link"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "definition",
    [
        "> [guide]: missing.md",
        "- [guide]: missing.md",
        "> - [guide]: missing.md",
        "1. > [guide]: missing.md",
        "-\t[guide]: missing.md",
        ">\t[guide]: missing.md",
        ">\t-\t[guide]: missing.md",
        "> \t[guide]: missing.md",
        ">  \t[guide]: missing.md",
    ],
)
def test_reference_definitions_inside_containers_are_rejected(tmp_path, definition):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n{definition}\n\n[Guide][guide]\n")
    with pytest.raises(CollectionError, match="reference-style links are not allowed"):
        assemble(m, tmp_path / "out", p, d)


def test_unlisted_link_target_must_exist_at_exact_content_commit(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text("# P\n\n[Future](future.md)\n")
    git(p, "add", "README.md")
    git(p, "commit", "-qm", "link before target")
    content = git(p, "rev-parse", "HEAD")
    (p / "future.md").write_text("# Future\n")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "future.md", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "add target later")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="broken or unsafe relative link"):
        assemble(m, tmp_path / "out", p, d)


def test_unlisted_link_target_cannot_be_a_git_symlink(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text("# P\n\n[Alias](alias.md)\n")
    (p / "target.md").write_text("# Target\n")
    (p / "alias.md").symlink_to("target.md")
    git(p, "add", "README.md", "target.md", "alias.md")
    git(p, "commit", "-qm", "symlink target")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve symlink source revision")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="broken or unsafe relative link"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "html",
    [
        "<script>alert(1)</script>",
        '<iframe src="https://example.invalid"></iframe>',
        '<object data="payload"></object>',
        '<embed src="payload">',
        '<p onclick="alert(1)">active</p>',
        '<a href="javascript:alert(1)">active</a>',
        '<a\n href="javascript:alert(1)">active</a>',
        '<div style="background-image:url(https://example.invalid/track)"></div>',
        '<img srcset="https://example.invalid/track 1x">',
        '<q\n cite="https://example.invalid/track">active</q>',
    ],
)
def test_raw_html_is_rejected_from_imported_markdown(tmp_path, html):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n{html}\n")
    with pytest.raises(CollectionError, match="active raw HTML is not allowed"):
        assemble(m, tmp_path / "out", p, d)


def test_raw_html_examples_inside_code_are_inert(tmp_path):
    text = "# P\n\n`<img src=tracker.png>`\n\n```html\n<script>alert(1)</script>\n```\n\n    <iframe src=tracker.html></iframe>\n"
    m, p, d = fixture(tmp_path, ptext=text)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    validate(m, out)


@pytest.mark.parametrize("definition", ["[guide]: other.md", "[logo]: image.png"])
def test_reference_style_links_are_rejected(tmp_path, definition):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n{definition}\n")
    with pytest.raises(CollectionError, match="reference-style links are not allowed"):
        assemble(m, tmp_path / "out", p, d)


def test_markdown_autolink_is_not_mistaken_for_raw_html(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\n<https://example.com/>\n")
    out = tmp_path / "out"
    assemble(m, out, p, d)
    assert "<https://example.com/>" in (out / "pydasc/index.md").read_text()


def test_inert_angle_bracket_placeholder_is_not_mistaken_for_active_html(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\nrevision: <git-sha>\n")
    out = tmp_path / "out"
    assemble(m, out, p, d)
    assert "<git-sha>" in (out / "pydasc/index.md").read_text()


def test_unapproved_image_is_rejected(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\n![License](LICENSE)\n")
    with pytest.raises(CollectionError, match="image is not approved"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/image.png",
        "http://example.com/image.png",
        "mailto:image@example.com",
        "#image",
        "?image=1",
        "",
    ],
)
def test_remote_images_are_rejected(tmp_path, target):
    m, p, d = fixture(tmp_path, ptext=f"# P\n\n![Remote]({target})\n")
    with pytest.raises(CollectionError, match="image is not approved"):
        assemble(m, tmp_path / "out", p, d)


def test_approved_image_is_relocated_and_copied(tmp_path):
    m, p, d = fixture(tmp_path)
    (p / "README.md").write_text("# P\n\n![Plot](plot.png)\n")
    image = b"\x89PNG\r\n\x1a\nfixture"
    (p / "plot.png").write_bytes(image)
    git(p, "add", "README.md", "plot.png")
    git(p, "commit", "-qm", "image content")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract["files"].append(
        {
            "source": "plot.png",
            "destination": "pydasc/assets/plot.png",
            "media_type": "image/png",
            "documentation_status": {"label": "Reviewed", "evidence": "test"},
            "redistribution": {"spdx_license": "MIT", "license_file": "LICENSE"},
        }
    )
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve image")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["files"].append(
        {"source": "plot.png", "destination": "pydasc/assets/plot.png"}
    )
    m.write_text(yaml.safe_dump(data))
    out = tmp_path / "out"
    assemble(m, out, p, d)
    assert "![Plot](assets/plot.png)" in (out / "pydasc/index.md").read_text()
    assert (out / "pydasc/assets/plot.png").read_bytes() == image


def test_markdown_policy_extensions_match_mkdocs_configuration():
    root = Path(__file__).parents[1]
    configured = yaml.safe_load((root / "mkdocs.yml").read_text())[
        "markdown_extensions"
    ]
    names = [
        entry if isinstance(entry, str) else next(iter(entry)) for entry in configured
    ]
    assert names == MARKDOWN_POLICY_EXTENSIONS


def test_attr_list_event_handler_on_a_link_is_rejected(tmp_path):
    m, p, d = fixture(
        tmp_path, ptext='# P\n\n[Link](https://example.com/){onclick="alert(1)"}\n'
    )
    with pytest.raises(CollectionError, match="unsafe rendered attribute"):
        assemble(m, tmp_path / "out", p, d)


def test_attr_list_event_handler_on_image_is_rejected(tmp_path):
    m, p, d = fixture(
        tmp_path, ptext='# P\n\n![alt](https://example.com/x.png){onerror="alert(1)"}\n'
    )
    with pytest.raises(CollectionError, match="unsafe rendered attribute"):
        assemble(m, tmp_path / "out", p, d)


def test_fence_glued_to_list_marker_does_not_hide_raw_script(tmp_path):
    m, p, d = fixture(
        tmp_path, ptext="# P\n\n- ~~~html\n  <script>alert(1)</script>\n  ~~~\n"
    )
    with pytest.raises(CollectionError, match="active rendered HTML"):
        assemble(m, tmp_path / "out", p, d)


def test_indented_code_inside_blockquote_is_not_a_live_link(tmp_path):
    m, p, d = fixture(
        tmp_path, ptext="# P\n\n> quote\n>\n>     [literal](<guide file.md>)\n"
    )
    assemble(m, tmp_path / "out", p, d)


def test_html_entity_in_destination_resolves_to_approved_file(tmp_path):
    m, p, d = fixture(tmp_path, ptext="# P\n\n[Home](README&#46;md)\n")
    out = tmp_path / "out"
    assemble(m, out, p, d)
    validate(m, out)
    assert "[Home](index.md)" in (out / "pydasc/index.md").read_text()


def test_duplicate_href_cannot_hide_unsafe_url_in_masked_html(tmp_path):
    text = (
        "# P\n\n<!-- [Example](https://example.com/) -->\n\n"
        "- ~~~html\n"
        '  <a href="javascript:alert(1)" HREF="https://example.com/">Link</a>\n'
        "  ~~~\n"
    )
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    with pytest.raises(CollectionError, match="duplicate HTML attribute: href"):
        assemble(manifest, tmp_path / "out", pydasc, dasc)


@pytest.mark.parametrize(
    "html,pattern",
    [
        ('<a href="javascript:alert(1)">Link</a>', "unsafe link"),
        ('<a href="jav&#x61;script:alert(1)">Link</a>', "unsafe link"),
        ('<a href="java&#9;script:alert(1)">Link</a>', "unsafe rendered URL"),
        ('<img src="https://example.com/x.png">', "image is not approved"),
        (
            '<img src="data:text/html,active" src="approved.png">',
            "duplicate HTML attribute",
        ),
    ],
)
def test_rendered_urls_are_checked_without_source_matches(html, pattern):
    from pathlib import PurePosixPath

    text = f"# P\n\n- ~~~html\n  {html}\n  ~~~\n"
    with pytest.raises(CollectionError, match=pattern):
        collect_docs._markdown_link_matches(text, PurePosixPath("README.md"))


@pytest.mark.parametrize(
    "destination",
    [
        "https://example.com/a&#41;b",
        "https://example.com/a&#32;b?q=&quot;quoted&quot;&amp;x=1",
        "https://example.com/?q=&amp;copy;",
        "?q=&#41;&amp;x=&#32;#part",
        "#part&#41;with&#32;space",
    ],
)
def test_unchanged_urls_preserve_entities_and_rendered_destinations(
    tmp_path, destination
):
    import markdown
    from html import unescape

    text = f"# P\n\n[Link]({destination})\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert f"[Link]({destination})" in generated
    parser = collect_docs.RenderedReferenceParser()
    parser.feed(markdown.markdown(generated, extensions=MARKDOWN_POLICY_EXTENSIONS))
    assert ("link", unescape(destination)) in parser.references


def test_rewritten_query_and_fragment_are_safe_markdown(tmp_path):
    text = "# P\n\n[Home](README&#46;md?q=&#41;&amp;name=&#32;&amp;literal=%26copy%3B#part&#40;)\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert (
        "[Home](index.md?q=%29&amp;name=%20&amp;literal=%26copy%3B#part%28)"
        in generated
    )


@pytest.mark.parametrize(
    "literal",
    [
        "<!-- [Example](README.md) -->",
        "<!--\n~~~\n[Example](README.md)\n~~~\n-->",
        "`[Example](README.md)`",
        ">     [Example](README.md)",
        "<div>\n[Example](README.md)\n</div>",
    ],
)
def test_literal_link_occurrence_cannot_consume_visible_matches(tmp_path, literal):
    text = f"# P\n\n{literal}\n\n[Home](README.md)\n\n[Again](README.md)\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert literal in generated
    assert "[Home](index.md)" in generated
    assert "[Again](index.md)" in generated
    assert "dasc-policy-" not in generated


def test_unsupported_link_examples_in_comments_are_ignored(tmp_path):
    text = "# P\n\n<!-- [Example](<guide file.md>) -->\n\n[Home](README.md)\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert (
        "<!-- [Example](<guide file.md>) -->"
        in (output / "pydasc/index.md").read_text()
    )


def test_autolink_comment_cannot_hide_unsupported_raw_anchor():
    from pathlib import PurePosixPath

    text = (
        "# P\n\n<!-- <https://example.com/> -->\n\n"
        '- ~~~html\n  <a href="https://example.com/">Link</a>\n  ~~~\n'
    )
    with pytest.raises(
        CollectionError, match="unsupported rendered Markdown link syntax"
    ):
        collect_docs._markdown_link_matches(text, PurePosixPath("README.md"))


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/a)b",
        "user@example.com",
        "https://example.com/?a=1&b=2",
    ],
)
def test_autolink_occurrences_preserve_url_syntax(target):
    from pathlib import PurePosixPath

    text = f"<!-- <{target}> -->\n\n<{target}>\n"
    assert collect_docs._markdown_link_matches(text, PurePosixPath("README.md")) == []


def test_live_link_in_fence_like_list_is_rewritten(tmp_path):
    text = "# P\n\n> - ~~~markdown\n>   [Home](README.md)\n>   ~~~\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert "[Home](index.md)" in (output / "pydasc/index.md").read_text()
