"""Preserve the first reported failure when multiple publication defects exist."""

import hashlib
import json
import sys

import pytest

from source_fixtures import fixture
from collect_docs import CollectionError, assemble
from validate_docs import main, validate


@pytest.mark.parametrize(
    "case",
    [
        "inventory-before-tree",
        "selection-before-tree",
        "tree-before-provenance",
        "provenance-before-checksum",
        "checksum-before-decode",
        "decode-before-banner",
        "banner-before-links",
        "file-order",
        "reversed-file-order",
    ],
)
def test_validation_reports_first_failure(tmp_path, case):
    manifest, pydasc, dasc = fixture(tmp_path)
    docs = tmp_path / "output"
    assemble(manifest, docs, pydasc, dasc)
    inventory_path = docs / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_bytes())
    if case == "reversed-file-order":
        inventory["files"].reverse()
    first, second = inventory["files"]
    relative = first["destination"]
    path = docs / relative
    error_type = CollectionError

    if case in {
        "inventory-before-tree",
        "selection-before-tree",
        "tree-before-provenance",
    }:
        (docs / "pydasc/extra.md").write_text("# Unexpected\n")
        if case == "inventory-before-tree":
            inventory["schema_version"] = 2
            message = "invalid inventory schema"
        elif case == "selection-before-tree":
            inventory["files"].remove(first)
            message = f"inventory differs from manifest: missing=['{relative}'], unexpected=[]"
        else:
            first["repository"] = "wrong repository"
            message = "output boundary differs: missing=[], unexpected=['pydasc/extra.md']"
    elif case == "provenance-before-checksum":
        first["repository"] = "wrong repository"
        path.write_bytes(b"changed")
        message = f"inventory provenance differs from manifest: {relative}"
    elif case in {"checksum-before-decode", "decode-before-banner"}:
        path.write_bytes(b"\xff")
        if case == "checksum-before-decode":
            message = f"checksum mismatch: {relative}"
        else:
            first["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            error_type = UnicodeDecodeError
            message = "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"
    else:
        text = path.read_text()
        if case == "banner-before-links":
            text = "# Missing provenance\n"
            message = f"unsafe/missing provenance: {relative}"
        else:
            second["repository"] = "wrong repository"
            message = f"broken link: {relative}: missing.md"
        path.write_text(text + "\n[Missing](missing.md)\n")
        first["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(error_type) as error:
        validate(manifest, docs)
    assert str(error.value) == message


def test_validation_cli_preserves_controlled_error_output(tmp_path, monkeypatch, capsys):
    manifest, pydasc, dasc = fixture(tmp_path)
    docs = tmp_path / "output"
    assemble(manifest, docs, pydasc, dasc)
    (docs / "generated-inventory.json").write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_docs.py",
            "--manifest",
            str(manifest),
            "--docs",
            str(docs),
        ],
    )

    assert main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "error: invalid inventory schema\n"
