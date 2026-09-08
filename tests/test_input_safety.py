"""Adversarial coverage of file and schema boundaries, independent of Markdown."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest
import yaml

from test_docs import fixture, git, hashes
import collect_docs as collector
import validate_docs as validator


@pytest.fixture(scope="module")
def approved_sources(tmp_path_factory):
    return fixture(tmp_path_factory.mktemp("approved-inputs"))


def special_entry(path, kind):
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    elif kind == "socket":
        # Unix socket names have a small length limit, so bind relative to dir.
        sock = socket.socket(socket.AF_UNIX)
        try:
            sock.bind(str(path))
        finally:
            sock.close()
    else:
        path.symlink_to(path.with_name("missing"))


@pytest.mark.parametrize("kind", ["fifo", "directory", "socket", "symlink"])
def test_regular_reader_rejects_special_entries_before_open(tmp_path, monkeypatch, kind):
    path = tmp_path / "input"
    # Use relative names to stay below the platform's Unix socket path limit.
    monkeypatch.chdir(tmp_path)
    special_entry(Path("input"), kind)
    monkeypatch.setattr(collector.os, "open", lambda *a, **k: pytest.fail("opened a special file"))
    with pytest.raises(collector.CollectionError, match="regular file"):
        collector._read_regular_file(path, "test input")


@pytest.mark.parametrize("kind", ["fifo", "symlink", "regular"])
def test_regular_reader_rejects_swaps_between_check_and_open(tmp_path, monkeypatch, kind):
    path = tmp_path / "input"
    path.write_bytes(b"original")
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"replacement")
    original_open = os.open

    def swapped_open(filename, flags, *args, **kwargs):
        assert flags & os.O_NONBLOCK
        assert flags & os.O_NOFOLLOW
        # Renaming keeps the original inode allocated, making the identity
        # assertion independent of immediate inode reuse on the filesystem.
        path.rename(tmp_path / "previous")
        if kind == "regular":
            replacement.rename(path)
        elif kind == "symlink":
            path.symlink_to(replacement)
        else:
            os.mkfifo(path)
        return original_open(filename, flags, *args, **kwargs)

    monkeypatch.setattr(collector.os, "open", swapped_open)
    with pytest.raises(collector.CollectionError, match="test input"):
        collector._read_regular_file(path, "test input")


def test_regular_reader_limits_size(tmp_path, monkeypatch):
    path = tmp_path / "input"
    path.write_bytes(b"12345")
    monkeypatch.setattr(collector, "MAX_FILE_BYTES", 4)
    with pytest.raises(collector.CollectionError, match="oversized"):
        collector._read_regular_file(path, "test input")


def test_source_integrity_hashes_unusual_names_and_large_unpublished_files(tmp_path, monkeypatch):
    _, pydasc, _ = fixture(tmp_path)
    files = ["space name.txt", 'quote"name.txt', "line\nbreak.txt", "한글.txt"]
    for name in files:
        (pydasc / name).write_bytes(b"unpublished bytes")
    monkeypatch.setattr(collector, "MAX_FILE_BYTES", 1)
    before = collector._tree_state(pydasc)
    assert set(files) <= {name for name, digest in before[1]}
    # Changing a same-length untracked file leaves porcelain status unchanged;
    # its content hash must still cause the source-integrity comparison to fail.
    for name in files:
        (pydasc / name).write_bytes(b"different content")
        assert collector._tree_state(pydasc) != before
        (pydasc / name).write_bytes(b"unpublished bytes")


@pytest.mark.parametrize("target", ["website", "contract"])
@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_manifest_cli_rejects_special_files_without_hanging(tmp_path, target, kind):
    manifest, pydasc, dasc = fixture(tmp_path)
    path = manifest if target == "website" else pydasc / "docs/publication-manifest.json"
    path.unlink()
    special_entry(path, kind)
    output = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(Path(collector.__file__)), "--manifest", str(manifest),
         "--output", str(output), "--pydasc", str(pydasc), "--dasc", str(dasc)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert "regular file" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("kind", ["fifo", "socket"])
def test_output_tree_rejects_unlisted_special_files(tmp_path, monkeypatch, approved_sources, kind):
    manifest, pydasc, dasc = approved_sources
    output = tmp_path / "out"
    collector.assemble(manifest, output, pydasc, dasc)
    monkeypatch.chdir(output / "pydasc")
    special_entry(Path("unexpected.md"), kind)
    with pytest.raises(collector.CollectionError, match="unsafe output entry"):
        validator.validate(manifest, output)


def test_output_tree_does_not_suppress_inspection_errors(tmp_path, monkeypatch, approved_sources):
    manifest, pydasc, dasc = approved_sources
    output = tmp_path / "out"
    collector.assemble(manifest, output, pydasc, dasc)
    blocked = output / "pydasc/hidden"
    blocked.mkdir()
    original = os.scandir

    def denied(path):
        if Path(path) == blocked:
            raise PermissionError("inaccessible output subtree")
        return original(path)

    monkeypatch.setattr(validator.os, "scandir", denied)
    with pytest.raises(PermissionError, match="inaccessible output subtree"):
        validator.validate(manifest, output)


@pytest.mark.parametrize("value", [".", "./", "././", "", [], {}, None, True, 1])
def test_invalid_normalized_paths_are_controlled(value):
    with pytest.raises(collector.CollectionError):
        collector._path(value, "destination")


@pytest.mark.parametrize("value", [None, [], {}, True, False, 1, 1.0, ""])
def test_contract_wrong_field_types_are_controlled(approved_sources, value):
    _, pydasc, dasc = approved_sources
    for checkout in (pydasc, dasc):
        path = checkout / "docs/publication-manifest.json"
        original = json.loads(path.read_bytes())
        fields = [
            ("schema_version",), ("project",), ("repository",), ("source_commit",),
            ("files",), ("files", 0), ("files", 0, "source"), ("files", 0, "destination"),
            ("files", 0, "media_type"), ("files", 0, "documentation_status"),
            ("files", 0, "documentation_status", "label"),
            ("files", 0, "documentation_status", "evidence"),
            ("files", 0, "redistribution"), ("files", 0, "redistribution", "spdx_license"),
            ("files", 0, "redistribution", "license_file"),
        ]
        if checkout == dasc:
            fields += [("publication_decision",), ("publication_decision", "state"),
                       ("publication_decision", "reason"), ("publication_decision", "evidence"),
                       ("files", 0, "redistribution", "attribution")]
        for field in fields:
            # schema 1 and an empty list of upstream offers are valid values.
            if field == ("schema_version",) and type(value) is int and value == 1:
                continue
            if field == ("files",) and value == []:
                continue
            contract = copy.deepcopy(original)
            parent = contract
            for key in field[:-1]:
                parent = parent[key]
            parent[field[-1]] = value
            with pytest.raises(collector.CollectionError):
                collector._source_contract(path, checkout.name, collector.EXPECTED[checkout.name],
                                           git(checkout, "rev-parse", "HEAD"), json.dumps(contract).encode())


@pytest.mark.parametrize("value", [None, [], {}, True, 1, 2.0, ""])
def test_website_wrong_field_types_are_controlled(tmp_path, approved_sources, value):
    manifest, _, _ = approved_sources
    original = yaml.safe_load(manifest.read_text())
    fields = [("schema_version",), ("sources",), ("sources", "pydasc")]
    fields += [("sources", "pydasc", key) for key in
               ("repository", "checkout_commit", "publication_manifest", "files")]
    fields += [("sources", "pydasc", "files", 0, key) for key in ("source", "destination")]
    for field in fields:
        data = copy.deepcopy(original)
        parent = data
        for key in field[:-1]:
            parent = parent[key]
        parent[field[-1]] = value
        path = tmp_path / "manifest.yml"
        path.write_text(yaml.safe_dump(data))
        with pytest.raises(collector.CollectionError):
            collector.load_manifest(path)


@pytest.mark.parametrize("text", [
    "schema_version: 2\nschema_version: 2\nsources: {}\n",
    "schema_version: 2\nsources: {}\nnull: 1\n3: 2\n",
    "schema_version: 2\nsources: {pydasc: {}, pydasc: {}}\n",
])
def test_yaml_duplicate_and_non_string_keys_are_rejected(tmp_path, text):
    path = tmp_path / "manifest.yml"
    path.write_text(text)
    with pytest.raises(collector.CollectionError):
        collector.load_manifest(path)


def test_mixed_unknown_keys_do_not_crash_error_reporting():
    with pytest.raises(collector.CollectionError, match="keys invalid"):
        collector._mapping({None: 1, 2: 1, "unknown": 1}, {"schema_version"}, "test")


@pytest.mark.parametrize("text", [b'{"files":[],"files":[]}', b'{"file":{"source":1,"source":2}}', b'[' * 2000])
def test_invalid_json_is_controlled(text):
    with pytest.raises(collector.CollectionError):
        collector._read_json(text, "test manifest")


@pytest.mark.parametrize("value", [None, [], {}, True, 1.0, ""])
def test_inventory_wrong_field_types_are_controlled(tmp_path, approved_sources, value):
    manifest, pydasc, dasc = approved_sources
    output = tmp_path / "out"
    collector.assemble(manifest, output, pydasc, dasc)
    path = output / "generated-inventory.json"
    original = json.loads(path.read_bytes())
    fields = [("schema_version",), ("files",), ("files", 0)]
    fields += [("files", 0, key) for key in original["files"][0]]
    for field in fields:
        # Empty attribution is valid for PyDASC only; test the required DASC
        # attribution below through the inventory's first (dasc) entry.
        data = copy.deepcopy(original)
        parent = data
        for key in field[:-1]:
            parent = parent[key]
        parent[field[-1]] = value
        path.write_text(json.dumps(data))
        with pytest.raises(collector.CollectionError):
            validator.validate(manifest, output)


def test_inventory_duplicate_keys_are_rejected(tmp_path, approved_sources):
    manifest, pydasc, dasc = approved_sources
    output = tmp_path / "out"
    collector.assemble(manifest, output, pydasc, dasc)
    path = output / "generated-inventory.json"
    path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
    with pytest.raises(collector.CollectionError, match="duplicate JSON key"):
        validator.validate(manifest, output)


@pytest.mark.parametrize("field,value", [("destination", "."), ("destination", "././"), ("source", ".")])
def test_bad_path_cli_has_no_traceback(tmp_path, approved_sources, field, value):
    source_manifest, pydasc, dasc = approved_sources
    data = yaml.safe_load(source_manifest.read_text())
    data["sources"]["pydasc"]["files"][0][field] = value
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump(data))
    result = subprocess.run(
        [sys.executable, str(Path(collector.__file__)), "--manifest", str(manifest),
         "--output", str(tmp_path / "out"), "--pydasc", str(pydasc), "--dasc", str(dasc)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("location", ["publication.json", "docs/nested/publication.json"])
def test_contract_location_is_not_assumed_to_be_one_directory_deep(tmp_path, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    previous = pydasc / "docs/publication-manifest.json"
    relocated = pydasc / location
    relocated.parent.mkdir(parents=True, exist_ok=True)
    previous.rename(relocated)
    git(pydasc, "add", "-A")
    git(pydasc, "commit", "-qm", "relocate test contract")
    data = yaml.safe_load(manifest.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(pydasc, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["publication_manifest"] = location
    manifest.write_text(yaml.safe_dump(data))
    output = tmp_path / "out"
    before = hashes(pydasc)
    collector.assemble(manifest, output, pydasc, dasc)
    validator.validate(manifest, output)
    assert hashes(pydasc) == before
