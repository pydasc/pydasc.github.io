"""Publication approvals, source integrity, manifest and inventory contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import collect_docs
from collect_docs import CollectionError, assemble, load_manifest
from validate_docs import validate

from .publication_support import fixture, git


def test_commit_mismatch_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = "a" * 40
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="commit mismatch"):
        assemble(m, tmp_path / "out", p, d)


def test_dirty_publication_manifest_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["files"][0]["documentation_status"]["evidence"] = "uncommitted approval"
    contract_path.write_text(json.dumps(contract))
    with pytest.raises(CollectionError, match="differs from locked commit"):
        assemble(m, tmp_path / "out", p, d)


def test_transferred_repository_identity_is_accepted_from_exact_alias(tmp_path):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["repository"] = "https://github.com/chongshikpark/pydasc"
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "pre-transfer contract")
    commit = git(p, "rev-parse", "HEAD")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = commit
    m.write_text(yaml.safe_dump(data))
    assemble(m, tmp_path / "accepted", p, d)


def test_unrecognized_repository_identity_is_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["repository"] = "https://github.com/example/pydasc"
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "unrecognized repository")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="publication identity"):
        assemble(m, tmp_path / "rejected", p, d)


@pytest.mark.parametrize("collision", ["source", "destination"])
def test_duplicate_upstream_contract_paths_rejected_case_insensitively(
    tmp_path, collision
):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    duplicate = json.loads(json.dumps(contract["files"][0]))
    if collision == "source":
        duplicate["source"] = "readme.MD"
        duplicate["destination"] = "pydasc/other.md"
    else:
        duplicate["source"] = "OTHER.md"
        duplicate["destination"] = "pydasc/INDEX.md"
    contract["files"].append(duplicate)
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "duplicate contract path")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match=f"duplicate approved {collision}"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    ("section", "field", "value", "pattern"),
    [
        ("decision", "reason", "", "decision evidence"),
        ("decision", "evidence", 7, "decision evidence"),
        ("attribution", "attribution", "", "attribution"),
        ("attribution", "attribution", ["invalid"], "attribution"),
        ("attribution", "attribution", "<b>unsafe</b>", "attribution"),
        ("attribution", "attribution", "invalid--comment", "attribution"),
    ],
)
def test_dasc_decision_evidence_and_attribution_must_be_nonempty_strings(
    tmp_path, section, field, value, pattern
):
    m, p, d = fixture(tmp_path)
    contract_path = d / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    if section == "decision":
        contract["publication_decision"][field] = value
    else:
        contract["files"][0]["redistribution"][field] = value
    contract_path.write_text(json.dumps(contract))
    git(d, "add", "docs/publication-manifest.json")
    git(d, "commit", "-qm", "invalid publication metadata")
    data = yaml.safe_load(m.read_text())
    data["sources"]["dasc"]["checkout_commit"] = git(d, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match=pattern):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize("value", ["/README.md", "../README.md", "*.md", "secret.env"])
def test_unsafe_selection_rejected(tmp_path, value):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["files"][0]["source"] = value
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "value", ["bad\nname.md", "bad\tname.md", "bad`name.md", "bad\x7fname.md"]
)
def test_manifest_paths_reject_controls_and_markdown_delimiters(tmp_path, value):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["files"][0]["destination"] = f"pydasc/{value}"
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="POSIX path"):
        load_manifest(m)


def test_unapproved_and_casefold_collision_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["files"].append(
        {"source": "README.md", "destination": "pydasc/INDEX.md"}
    )
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="duplicate"):
        assemble(m, tmp_path / "out", p, d)


def test_license_must_be_a_regular_git_blob(tmp_path):
    m, p, d = fixture(tmp_path)
    license_path = p / "LICENSE"
    license_path.unlink()
    license_path.symlink_to("README.md")
    git(p, "add", "LICENSE")
    git(p, "commit", "-qm", "symlink license")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "contract with symlink license")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="unsafe license"):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "destination",
    ["/pydasc/index.md", "../index.md", "pydasc/../index.md", "dasc/index.md"],
)
def test_unsafe_destination_rejected(tmp_path, destination):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["files"][0]["destination"] = destination
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError):
        assemble(m, tmp_path / "out", p, d)


@pytest.mark.parametrize(
    "mutation", ["schema", "root_key", "source_key", "repository", "short_commit"]
)
def test_manifest_schema_identity_and_unknown_keys_rejected(tmp_path, mutation):
    m, p, d = fixture(tmp_path)
    data = yaml.safe_load(m.read_text())
    if mutation == "schema":
        data["schema_version"] = 999
    elif mutation == "root_key":
        data["unexpected"] = True
    elif mutation == "source_key":
        data["sources"]["pydasc"]["unexpected"] = True
    elif mutation == "repository":
        data["sources"]["pydasc"]["repository"] = "https://github.com/example/pydasc"
    else:
        data["sources"]["pydasc"]["checkout_commit"] = "abc123"
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError):
        load_manifest(m)


def test_source_symlink_and_non_regular_file_rejected(tmp_path):
    for kind in ("symlink", "directory"):
        root = tmp_path / kind
        root.mkdir()
        m, p, d = fixture(root)
        source = p / "README.md"
        source.unlink()
        if kind == "symlink":
            outside = root / "outside.md"
            outside.write_text("outside\n")
            source.symlink_to(outside)
        else:
            source.mkdir()
        with pytest.raises(CollectionError, match="unsafe or missing source"):
            assemble(m, root / "out", p, d)


def test_oversized_source_rejected(tmp_path, monkeypatch):
    m, p, d = fixture(tmp_path, ptext="# P\n" + "x" * 2048)
    monkeypatch.setattr(collect_docs, "MAX_FILE_BYTES", 1024)
    with pytest.raises(CollectionError, match="oversized source"):
        assemble(m, tmp_path / "out", p, d)


def test_approved_but_missing_source_is_rejected(tmp_path):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["files"].append(
        {
            "source": "missing.md",
            "destination": "pydasc/missing.md",
            "media_type": "text/markdown",
            "documentation_status": {"label": "Reviewed", "evidence": "test"},
            "redistribution": {"spdx_license": "MIT", "license_file": "LICENSE"},
        }
    )
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve missing file")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["files"].append(
        {"source": "missing.md", "destination": "pydasc/missing.md"}
    )
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="unsafe or missing source"):
        assemble(m, tmp_path / "out", p, d)


def test_dasc_attribution_is_preserved_in_output_and_inventory(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    inventory = assemble(m, out, p, d)
    generated = (out / "dasc/index.md").read_text()
    dasc_item = next(
        item for item in inventory if item["destination"] == "dasc/index.md"
    )
    assert dasc_item["attribution"] == "Test"
    assert "attribution=Test" in generated
    assert "**Attribution:** Test" in generated
    validate(m, out)


@pytest.mark.parametrize(
    "payload",
    [
        "<svg><script>alert(1)</script></svg>",
        '<svg onload="alert(1)"></svg>',
        "<svg><foreignObject><div>active</div></foreignObject></svg>",
        '<svg><image href="https://example.invalid/tracker.png"/></svg>',
    ],
)
def test_svg_publication_is_rejected(tmp_path, payload):
    m, p, d = fixture(tmp_path)
    (p / "attack.svg").write_text(payload)
    git(p, "add", "attack.svg")
    git(p, "commit", "-qm", "svg content")
    content = git(p, "rev-parse", "HEAD")
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["source_commit"] = content
    contract["files"].append(
        {
            "source": "attack.svg",
            "destination": "pydasc/assets/attack.svg",
            "media_type": "image/svg+xml",
            "documentation_status": {"label": "Reviewed", "evidence": "test"},
            "redistribution": {"spdx_license": "MIT", "license_file": "LICENSE"},
        }
    )
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "approve svg")
    data = yaml.safe_load(m.read_text())
    data["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    data["sources"]["pydasc"]["files"].append(
        {"source": "attack.svg", "destination": "pydasc/assets/attack.svg"}
    )
    m.write_text(yaml.safe_dump(data))
    with pytest.raises(CollectionError, match="invalid approved file"):
        assemble(m, tmp_path / "out", p, d)


def test_inventory_must_match_manifest_selection_and_provenance(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    inventory_path = out / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["files"][0]["source"] = "UNLISTED.md"
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match="provenance differs from manifest"):
        validate(m, out)
    assemble(m, out, p, d)
    inventory = json.loads(inventory_path.read_text())
    item = next(
        entry
        for entry in inventory["files"]
        if entry["destination"] == "pydasc/index.md"
    )
    (out / "pydasc/index.md").rename(out / "pydasc/rogue.md")
    item["destination"] = "pydasc/rogue.md"
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match="inventory differs from manifest"):
        validate(m, out)


@pytest.mark.parametrize("bad_item", [None, [], {}, {"destination": "pydasc/index.md"}])
def test_malformed_inventory_item_has_controlled_error(tmp_path, bad_item):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    inventory_path = out / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["files"][0] = bad_item
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match="invalid inventory item"):
        validate(m, out)


def test_non_string_inventory_destination_has_controlled_error(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    inventory_path = out / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["files"][0]["destination"] = []
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match="invalid inventory destination"):
        validate(m, out)


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("commit", "not-a-commit", "inventory commit"),
        ("status", "Unknown", "inventory status"),
        ("license", "MIT OR", "inventory license"),
        ("attribution", "<unsafe>", "inventory attribution"),
    ],
)
def test_inventory_provenance_fields_are_validated(tmp_path, field, value, pattern):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    inventory_path = out / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["files"][0][field] = value
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match=pattern):
        validate(m, out)


def test_markdown_banner_must_match_inventory_provenance(tmp_path):
    m, p, d = fixture(tmp_path)
    out = tmp_path / "out"
    assemble(m, out, p, d)
    inventory_path = out / "generated-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["files"][0]["commit"] = "a" * 40
    inventory_path.write_text(json.dumps(inventory))
    with pytest.raises(CollectionError, match="unsafe/missing provenance"):
        validate(m, out)


def test_release_keeps_api_and_examples_static():
    root = Path(__file__).parents[1]
    data = yaml.safe_load((root / "docs-manifest.yml").read_text())
    selected = [
        entry["source"]
        for source in data["sources"].values()
        for entry in source["files"]
    ]
    assert "docs/PUBLIC_API.md" in selected
    assert all(not path.casefold().endswith(".ipynb") for path in selected)
    assert all(
        not any(
            part.casefold() in {"examples", "notebooks"} for part in Path(path).parts
        )
        for path in selected
    )
    requirements = (root / "requirements-docs.txt").read_text().casefold()
    assert all(
        tool not in requirements
        for tool in ("jupyter", "nbconvert", "mkdocstrings", "pydoc")
    )
