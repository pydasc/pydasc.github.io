"""Generated output containment, filesystem identities and atomic inventory writes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import collect_docs
from collect_docs import CollectionError, assemble
from validate_docs import validate

from .publication_support import fixture, git, hashes


def test_deterministic_inventory_validation_and_source_immutability(tmp_path):
    m, p, d = fixture(tmp_path)
    before = (hashes(p), hashes(d))
    out = tmp_path / "out"
    first = assemble(m, out, p, d)
    validate(m, out)
    second = assemble(m, out, p, d)
    assert first == second
    assert before == (hashes(p), hashes(d))
    assert len(first) == 2
    generated = (out / "pydasc/index.md").read_text()
    assert '!!! info "Publication record"' in generated
    assert "**Project:** PyDASC" in generated
    assert first[1]["commit"] in generated


def test_unknown_output_and_checksum_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    (out / "dasc/extra.md").write_text("x")
    with pytest.raises(CollectionError, match="boundary"):
        validate(m, out)


def test_stale_generated_file_is_removed_only_inside_namespace(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    stale = out / "pydasc/stale.md"
    stale.write_text("stale\n")
    portal = out / "portal.md"
    portal.write_text("keep\n")
    assemble(m, out, p, d)
    assert not stale.exists()
    assert portal.read_text() == "keep\n"


@pytest.mark.parametrize(
    "location", ["source", "inside", "ancestor", "alias", "alias_parent", "dotdot"]
)
def test_output_overlap_is_rejected_before_staging_or_source_inspection(
    tmp_path, monkeypatch, location
):
    manifest, pydasc, dasc = fixture(tmp_path)
    before = (hashes(pydasc), hashes(dasc))
    heads = (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))
    alias = tmp_path / "alias"
    alias.symlink_to(pydasc, target_is_directory=True)
    paths = {
        "source": pydasc,
        "inside": pydasc / "generated",
        "ancestor": tmp_path,
        "alias": alias,
        "alias_parent": alias / "generated",
        "dotdot": pydasc / "docs" / "..",
    }

    def unexpected_work(*args, **kwargs):
        pytest.fail("unsafe output must fail before source inspection or staging")

    monkeypatch.setattr(collect_docs, "_tree_state", unexpected_work)
    monkeypatch.setattr(collect_docs.tempfile, "TemporaryDirectory", unexpected_work)
    with pytest.raises(CollectionError, match="overlaps|unsafe output"):
        assemble(manifest, paths[location], pydasc, dasc)
    assert before == (hashes(pydasc), hashes(dasc))
    assert heads == (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))


@pytest.mark.parametrize(
    "location",
    [
        "pydasc",
        "dasc",
        "inside_existing",
        "inside_missing",
        "ancestor",
        "checkout_alias",
    ],
)
def test_case_alias_output_overlap_rejected_before_any_work(
    tmp_path, monkeypatch, location
):
    manifest, pydasc, dasc = fixture(tmp_path)
    alias = pydasc.with_name("PYDASC")
    if not alias.exists() or not alias.samefile(pydasc):
        pytest.skip("requires a case-insensitive filesystem")
    (pydasc / "generated").mkdir()
    output = {
        "pydasc": alias,
        "dasc": dasc.with_name("DASC"),
        "inside_existing": alias / "generated",
        "inside_missing": alias / "not-created" / "nested",
        "ancestor": tmp_path.with_name(tmp_path.name.upper()),
        "checkout_alias": pydasc / "not-created" / "nested",
    }[location]
    before = (hashes(pydasc), hashes(dasc))
    heads = (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))

    def unexpected_work(*args, **kwargs):
        pytest.fail("case aliases must fail before inspection, staging, or deletion")

    monkeypatch.setattr(collect_docs, "_tree_state", unexpected_work)
    monkeypatch.setattr(collect_docs.tempfile, "TemporaryDirectory", unexpected_work)
    monkeypatch.setattr(collect_docs.shutil, "rmtree", unexpected_work)
    with pytest.raises(CollectionError, match="overlaps"):
        assemble(
            manifest, output, alias if location == "checkout_alias" else pydasc, dasc
        )
    assert before == (hashes(pydasc), hashes(dasc))
    assert heads == (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))
    assert not (pydasc / "not-created").exists()


@pytest.mark.parametrize(
    "location", ["PYDASC/manifest.yml", "DASC/manifest.yml", "GENERATED-INVENTORY.JSON"]
)
def test_case_alias_output_cannot_replace_manifest(tmp_path, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    relocated = output / location
    relocated.parent.mkdir(parents=True)
    relocated.write_bytes(manifest.read_bytes())
    alias = output / location.lower()
    if not alias.exists() or not alias.samefile(relocated):
        pytest.skip("requires a case-insensitive filesystem")
    before = hashes(output)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(relocated, output, pydasc, dasc)
    assert hashes(output) == before


def test_filesystem_containment_walks_existing_alias_ancestors(tmp_path):
    # Exercise identity comparisons on case-sensitive CI too; resolve() is
    # deliberately not used here because it would remove this test alias.
    root = tmp_path / "source"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert collect_docs._filesystem_inside(alias, root)
    assert collect_docs._filesystem_inside(alias / "missing" / "nested", root)
    assert collect_docs._filesystem_inside(root / "missing" / "nested", alias)
    assert not collect_docs._filesystem_inside(tmp_path / "elsewhere", root)
    assert not collect_docs._filesystem_inside(root, tmp_path / "missing")


def test_filesystem_containment_does_not_fold_distinct_names(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    other = tmp_path / "SOURCE"
    if other.exists():
        pytest.skip("requires a case-sensitive filesystem")
    other.mkdir()
    assert not collect_docs._filesystem_inside(other / "missing", root)
    assert not collect_docs._filesystem_inside(root, other)


def test_output_identity_inspection_errors_fail_closed(tmp_path, monkeypatch):
    output = tmp_path / "out"
    checkout = tmp_path / "source"
    checkout.mkdir()
    original_stat = Path.stat

    def denied_stat(path, *args, **kwargs):
        if path == checkout:
            raise PermissionError("cannot inspect source identity")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied_stat)
    with pytest.raises(CollectionError, match="cannot inspect output paths"):
        collect_docs._preflight_output(
            output, {"pydasc": checkout}, tmp_path / "lock.yml"
        )
    assert not output.exists()


@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory", "fifo"])
def test_inventory_path_rejected_before_any_output_changes(tmp_path, kind):
    import os

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    before = (
        hashes(pydasc),
        hashes(dasc),
        hashes(output / "pydasc"),
        hashes(output / "dasc"),
    )
    external = tmp_path / "external.json"
    external.write_text("untouched")
    inventory = output / "generated-inventory.json"
    inventory.unlink()
    if kind == "symlink":
        inventory.symlink_to(external)
    elif kind == "dangling":
        inventory.symlink_to(tmp_path / "missing.json")
    elif kind == "directory":
        inventory.mkdir()
    else:
        os.mkfifo(inventory)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        assemble(manifest, output, pydasc, dasc)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        validate(manifest, output)
    assert before == (
        hashes(pydasc),
        hashes(dasc),
        hashes(output / "pydasc"),
        hashes(output / "dasc"),
    )
    assert external.read_text() == "untouched"
    assert not (tmp_path / "missing.json").exists()
    assert not list(output.glob(".generated-inventory-*.tmp"))


@pytest.mark.parametrize("kind", ["symlink", "dangling", "file"])
def test_all_namespaces_are_checked_before_replacing_first_namespace(tmp_path, kind):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    (output / "pydasc").mkdir(parents=True)
    (output / "pydasc/keep.txt").write_text("old output")
    (output / "generated-inventory.json").write_text("old inventory")
    if kind == "file":
        (output / "dasc").write_text("not a directory")
    else:
        (output / "dasc").symlink_to(
            dasc if kind == "symlink" else tmp_path / "missing",
            target_is_directory=True,
        )
    before = (hashes(pydasc), hashes(dasc))
    with pytest.raises(CollectionError, match="unsafe generated namespace"):
        assemble(manifest, output, pydasc, dasc)
    assert (output / "pydasc/keep.txt").read_text() == "old output"
    assert (output / "generated-inventory.json").read_text() == "old inventory"
    assert before == (hashes(pydasc), hashes(dasc))


@pytest.mark.parametrize(
    "location", ["pydasc/manifest.yml", "dasc/manifest.yml", "generated-inventory.json"]
)
def test_publication_cannot_overwrite_its_input_manifest(tmp_path, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    relocated = output / location
    relocated.parent.mkdir(parents=True)
    relocated.write_bytes(manifest.read_bytes())
    before = relocated.read_bytes()
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(relocated, output, pydasc, dasc)
    assert relocated.read_bytes() == before


def test_inventory_replacement_does_not_modify_a_hardlink_target(tmp_path):
    import os

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    external = tmp_path / "external.json"
    external.write_text("untouched")
    inventory = output / "generated-inventory.json"
    os.link(external, inventory)
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert external.read_text() == "untouched"
    assert not inventory.samefile(external)
    assert inventory.stat().st_mode & 0o777 == 0o644
    assert not list(output.glob(".generated-inventory-*.tmp"))


def test_failed_atomic_inventory_replace_preserves_previous_file(tmp_path, monkeypatch):
    inventory = tmp_path / "generated-inventory.json"
    inventory.write_text("old inventory")

    def fail_replace(source, destination):
        assert Path(source).parent == inventory.parent
        assert json.loads(Path(source).read_text()) == {
            "schema_version": 1,
            "files": [],
        }
        assert Path(destination) == inventory
        raise OSError("simulated replace failure")

    monkeypatch.setattr(collect_docs.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        collect_docs._write_inventory_atomic(inventory, [])
    assert inventory.read_text() == "old inventory"
    assert not list(tmp_path.glob(".generated-inventory-*.tmp"))


def test_output_paths_are_rechecked_after_staging(tmp_path, monkeypatch):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    before = (hashes(output / "pydasc"), hashes(output / "dasc"))
    external = tmp_path / "external.json"
    external.write_text("untouched")
    original = collect_docs._rewrite

    def change_inventory_after_preflight(*args, **kwargs):
        inventory = output / "generated-inventory.json"
        if not inventory.is_symlink():
            inventory.unlink()
            inventory.symlink_to(external)
        return original(*args, **kwargs)

    monkeypatch.setattr(collect_docs, "_rewrite", change_inventory_after_preflight)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        assemble(manifest, output, pydasc, dasc)
    assert before == (hashes(output / "pydasc"), hashes(output / "dasc"))
    assert external.read_text() == "untouched"


@pytest.mark.parametrize("kind", ["file", "symlink", "dangling"])
def test_invalid_output_root_is_rejected_without_changes(tmp_path, kind):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.txt").write_text("untouched")
    if kind == "file":
        output.write_text("untouched")
    else:
        output.symlink_to(
            external if kind == "symlink" else tmp_path / "missing",
            target_is_directory=True,
        )
    before = (hashes(pydasc), hashes(dasc), hashes(external))
    with pytest.raises(CollectionError, match="unsafe output directory"):
        assemble(manifest, output, pydasc, dasc)
    assert before == (hashes(pydasc), hashes(dasc), hashes(external))
    assert not (tmp_path / "missing").exists()


def test_manifest_symlink_inside_output_namespace_is_preserved(tmp_path):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    (output / "pydasc").mkdir(parents=True)
    alias = output / "pydasc/manifest.yml"
    alias.symlink_to(manifest)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(alias, output, pydasc, dasc)
    assert alias.is_symlink()
    assert alias.read_bytes() == manifest.read_bytes()
    parent_alias = tmp_path / "output-alias"
    parent_alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(parent_alias / "pydasc/manifest.yml", output, pydasc, dasc)
    assert alias.is_symlink()


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_validation_rejects_inventory_replaced_after_path_check(
    tmp_path, monkeypatch, kind
):
    import os
    import validate_docs

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    inventory = output / "generated-inventory.json"
    external = tmp_path / "external.json"
    external.write_bytes(inventory.read_bytes())
    original = validate_docs._check_inventory_path

    def change_entry(path, **kwargs):
        original(path, **kwargs)
        inventory.unlink()
        if kind == "symlink":
            inventory.symlink_to(external)
        else:
            os.mkfifo(inventory)

    monkeypatch.setattr(validate_docs, "_check_inventory_path", change_entry)
    with pytest.raises(CollectionError, match="invalid inventory|unsafe inventory"):
        validate(manifest, output)


def test_atomic_writer_rechecks_inventory_before_replacement(tmp_path, monkeypatch):
    inventory = tmp_path / "generated-inventory.json"
    inventory.write_text("previous")
    external = tmp_path / "external.json"
    external.write_text("untouched")

    def swap_during_write(fd):
        inventory.unlink()
        inventory.symlink_to(external)

    monkeypatch.setattr(collect_docs.os, "fsync", swap_during_write)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        collect_docs._write_inventory_atomic(inventory, [])
    assert external.read_text() == "untouched"
    assert not list(tmp_path.glob(".generated-inventory-*.tmp"))
