"""Exercise the shared release pipeline with real source repos and artifacts."""

from pathlib import Path
import os
import shutil

import pytest
import yaml

import check_release as release
from publication_io import MAX_FILE_BYTES
from publication_policy import CollectionError
from .publication_support import fixture, hashes


@pytest.fixture
def release_project(tmp_path):
    manifest, pydasc, dasc = fixture(tmp_path)
    manifest.rename(tmp_path / "docs-manifest.yml")
    docs = tmp_path / "docs"
    (docs / "stylesheets").mkdir(parents=True)
    (docs / "index.md").write_text("# Documentation\n")
    (docs / "dasc-foundations.md").write_text("# Foundations\n")
    shutil.copyfile(
        Path(__file__).parents[1] / "docs/stylesheets/readthedocs.css",
        docs / "stylesheets/readthedocs.css",
    )
    (tmp_path / "theme").mkdir()
    (tmp_path / "theme/main.html").write_text(
        '<!doctype html><html lang="en"><head><title>{{ page.title }}</title>'
        '<link href="{{ "stylesheets/readthedocs.css" | url }}" rel="stylesheet">'
        '</head><body><nav aria-label="Primary"></nav>'
        '<button data-dasc-drawer-control aria-controls="__drawer" '
        'aria-label="Open documentation navigation"></button>'
        "<main>{{ page.content }}</main></body></html>"
    )
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump(
            {
                "site_name": "Release fixture",
                "docs_dir": "docs",
                "site_dir": "site",
                "exclude_docs": "generated-inventory.json",
                "theme": {"name": None, "custom_dir": "theme"},
                "plugins": [],
                "markdown_extensions": ["admonition"],
                "nav": [
                    {"Home": "index.md"},
                    {"PyDASC": "pydasc/index.md"},
                    {"DASC": "dasc/index.md"},
                    {"Foundations": "dasc-foundations.md"},
                ],
            }
        )
    )
    return tmp_path, pydasc, dasc


def test_complete_release_builds_real_site_without_changing_sources(release_project):
    root, pydasc, dasc = release_project
    before = hashes(pydasc), hashes(dasc)
    release.check_release(root, pydasc, dasc)
    assert (root / "site/pydasc/index.html").is_file()
    assert (root / "site/dasc/index.html").is_file()
    assert before == (hashes(pydasc), hashes(dasc))


@pytest.mark.parametrize("defect", ["bytes", "empty-directory", "inventory"])
def test_nondeterminism_stops_before_build(release_project, monkeypatch, defect):
    root, pydasc, dasc = release_project
    original = release.assemble
    calls = 0

    def collect_then_change(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 2:
            if defect == "empty-directory":
                (root / "docs/pydasc/extra").mkdir()
            else:
                path = (
                    root
                    / "docs"
                    / (
                        "pydasc/index.md"
                        if defect == "bytes"
                        else "generated-inventory.json"
                    )
                )
                path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(release, "assemble", collect_then_change)
    with pytest.raises(CollectionError, match="differs between collections"):
        release.check_release(root, pydasc, dasc)
    assert calls == 2
    assert not (root / "site").exists()


@pytest.mark.parametrize(
    "payload",
    [
        b"github_pat_example",
        b"ghp_" + b"a" * 20,
        b"-----BEGIN PRIVATE KEY-----",
        b"-----BEGIN RSA PRIVATE KEY-----",
        b"-----BEGIN EC PRIVATE KEY-----",
        b"-----BEGIN OPENSSH PRIVATE KEY-----",
        b"/home/private/data",
        b"/Users/private/data",
        b"http://localhost/path",
        b"https://127.0.0.1/path",
        b"https://service.internal/path",
        b"\x00github_pat_example\x00",
    ],
    ids=[
        "pat",
        "classic-token",
        "key",
        "rsa",
        "ec",
        "openssh",
        "linux-path",
        "mac-path",
        "localhost",
        "loopback",
        "internal",
        "binary",
    ],
)
def test_artifact_scan_rejects_forbidden_bytes_without_echoing_them(tmp_path, payload):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/payload.bin").write_bytes(payload)
    with pytest.raises(CollectionError, match="forbidden credential-like") as error:
        release.scan_artifact(tmp_path)
    assert str(error.value).endswith("assets/payload.bin")
    assert payload.decode("utf-8") not in str(error.value)


@pytest.mark.parametrize(
    "kind", ["file-symlink", "directory-symlink", "dangling", "fifo"]
)
def test_artifact_scan_rejects_nonregular_entries(tmp_path, kind):
    site = tmp_path / "site"
    site.mkdir()
    target = site / "entry"
    if kind == "fifo":
        os.mkfifo(target)
    elif kind == "directory-symlink":
        target.symlink_to(tmp_path, target_is_directory=True)
    elif kind == "file-symlink":
        external = tmp_path / "outside.txt"
        external.write_text("external content")
        target.symlink_to(external)
    else:
        target.symlink_to(tmp_path / "missing")
    with pytest.raises(CollectionError, match="unsafe release entry"):
        release.scan_artifact(site)


def test_artifact_scan_rejects_oversized_file(tmp_path):
    with (tmp_path / "large.bin").open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)
    with pytest.raises(CollectionError, match="oversized site artifact"):
        release.scan_artifact(tmp_path)


def test_artifact_scan_rejects_unreadable_subtree(tmp_path, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    original = release.os.scandir

    def denied(path):
        if Path(path) == nested:
            raise PermissionError("cannot inspect subtree")
        return original(path)

    monkeypatch.setattr(release.os, "scandir", denied)
    with pytest.raises(PermissionError, match="cannot inspect subtree"):
        release.scan_artifact(tmp_path)


def test_site_output_cannot_overlap_source_checkout(release_project):
    root, pydasc, dasc = release_project
    pydasc.rename(root / "site")
    before = hashes(root / "site")
    with pytest.raises(CollectionError, match="overlaps a source checkout"):
        release.check_release(root, root / "site", dasc)
    assert hashes(root / "site") == before


def test_site_root_symlink_is_rejected_before_collection(release_project):
    root, pydasc, dasc = release_project
    (root / "site").symlink_to(pydasc, target_is_directory=True)
    before = hashes(pydasc)
    with pytest.raises(CollectionError, match="unsafe site output"):
        release.check_release(root, pydasc, dasc)
    assert hashes(pydasc) == before


def test_cli_reports_real_strict_build_failure(release_project, monkeypatch, capsys):
    root, pydasc, dasc = release_project
    config = root / "mkdocs.yml"
    value = yaml.safe_load(config.read_text())
    value["nav"].append({"Missing": "missing.md"})
    config.write_text(yaml.safe_dump(value))
    monkeypatch.setattr(release, "ROOT", root)
    assert release.main(["--pydasc", str(pydasc), "--dasc", str(dasc)]) == 1
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("gate", "message"),
    [
        ("source", "source differs from approved commit"),
        ("physics", "undefined equation reference"),
        ("links", "broken local reference"),
        ("accessibility", "missing document language"),
        ("artifact", "forbidden credential-like"),
    ],
)
def test_complete_release_rejects_each_invalid_input(
    release_project, capsys, gate, message
):
    root, pydasc, dasc = release_project
    template = root / "theme/main.html"
    if gate == "source":
        (pydasc / "README.md").write_text("# Changed since approval\n")
    elif gate == "physics":
        (root / "docs/dasc-invalid.md").write_text(
            "# Invalid\n\n[Missing](dasc-foundations.md#eq-missing)\n"
        )
    elif gate == "links":
        template.write_text(
            template.read_text().replace(
                "</main>", '<a href="missing.png">Missing</a></main>'
            )
        )
    elif gate == "accessibility":
        template.write_text(template.read_text().replace(' lang="en"', ""))
    else:
        (root / "docs/payload.txt").write_text("github_pat_example")
    with pytest.raises(ValueError, match=message):
        release.check_release(root, pydasc, dasc)
    assert "Release checks passed" not in capsys.readouterr().out
