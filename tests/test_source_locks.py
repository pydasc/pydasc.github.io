"""Candidate source-lock approvals, successful updates and failure handling."""

import json

import pytest
import yaml

from .publication_support import fixture, git, hashes
from collect_docs import CollectionError
from update_source_locks import main, update


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("changed", "source differs from approved commit"),
        ("missing", "unsafe or missing source"),
        ("symlink", "unsafe or missing source"),
        ("broken-link", "broken"),
    ],
)
def test_source_lock_rejects_uncollectable_candidate(tmp_path, case, message):
    manifest, pydasc, dasc = fixture(tmp_path)
    original_manifest = manifest.read_bytes()
    readme = pydasc / "README.md"
    if case == "changed":
        readme.write_text("# Changed after publication approval\n")
    elif case == "missing":
        readme.unlink()
    elif case == "symlink":
        readme.unlink()
        readme.symlink_to("LICENSE")
    else:
        readme.write_text("# Guide\n\n[Missing](missing.md)\n")
    git(pydasc, "add", "README.md")
    git(pydasc, "commit", "-qm", "candidate content")
    if case == "broken-link":
        # Even an approved revision must pass link/content collection checks.
        contract_path = pydasc / "docs/publication-manifest.json"
        contract = json.loads(contract_path.read_text())
        contract["source_commit"] = git(pydasc, "rev-parse", "HEAD")
        contract_path.write_text(json.dumps(contract))
        git(pydasc, "add", "docs/publication-manifest.json")
        git(pydasc, "commit", "-qm", "approve candidate content")
    source_hashes = (hashes(pydasc), hashes(dasc))

    with pytest.raises(CollectionError, match=message):
        update(manifest, {"pydasc": pydasc, "dasc": dasc})

    assert manifest.read_bytes() == original_manifest
    assert (hashes(pydasc), hashes(dasc)) == source_hashes


def test_skip_unapproved_does_not_hide_content_failure(tmp_path, capsys):
    manifest, pydasc, dasc = fixture(tmp_path)
    original_manifest = manifest.read_bytes()
    (pydasc / "README.md").write_text("# Changed after publication approval\n")
    git(pydasc, "add", "README.md")
    git(pydasc, "commit", "-qm", "candidate content")

    result = main(
        [
            "--skip-unapproved",
            "--manifest",
            str(manifest),
            "--pydasc",
            str(pydasc),
            "--dasc",
            str(dasc),
        ]
    )

    assert result == 1
    assert "source differs from approved commit" in capsys.readouterr().err
    assert manifest.read_bytes() == original_manifest


def test_source_lock_update_validates_candidate_and_changes_only_commit(tmp_path):
    m, p, d = fixture(tmp_path)
    before = yaml.safe_load(m.read_text())
    (p / "CHANGELOG.md").write_text("candidate\n")
    git(p, "add", "CHANGELOG.md")
    git(p, "commit", "-qm", "candidate")
    changes = update(m, {"pydasc": p, "dasc": d})
    after = yaml.safe_load(m.read_text())
    assert changes == {
        "pydasc": (
            before["sources"]["pydasc"]["checkout_commit"],
            git(p, "rev-parse", "HEAD"),
        )
    }
    assert after["sources"]["pydasc"]["checkout_commit"] == git(p, "rev-parse", "HEAD")
    before["sources"]["pydasc"]["checkout_commit"] = git(p, "rev-parse", "HEAD")
    assert after == before


def test_source_lock_update_accepts_transferred_repository_contract_alias(tmp_path):
    m, p, d = fixture(tmp_path)
    contract_path = p / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["repository"] = "https://github.com/chongshikpark/pydasc"
    contract_path.write_text(json.dumps(contract))
    git(p, "add", "docs/publication-manifest.json")
    git(p, "commit", "-qm", "transferred repository contract")
    previous = yaml.safe_load(m.read_text())["sources"]["pydasc"]["checkout_commit"]
    changes = update(m, {"pydasc": p, "dasc": d})
    assert changes == {"pydasc": (previous, git(p, "rev-parse", "HEAD"))}


def test_source_lock_cli_skips_unapproved_candidate_without_changes(tmp_path, capsys):
    m, p, d = fixture(tmp_path)
    before = m.read_bytes()
    contract_path = d / "docs/publication-manifest.json"
    contract = json.loads(contract_path.read_text())
    contract["publication_decision"]["state"] = "draft"
    contract_path.write_text(json.dumps(contract))
    git(d, "add", str(contract_path.relative_to(d)))
    git(d, "commit", "-qm", "draft contract")
    rejected = main(["--manifest", str(m), "--pydasc", str(p), "--dasc", str(d)])
    assert rejected == 1
    assert m.read_bytes() == before
    assert "error: DASC publication decision is not approved" in capsys.readouterr().err
    result = main(
        [
            "--skip-unapproved",
            "--manifest",
            str(m),
            "--pydasc",
            str(p),
            "--dasc",
            str(d),
        ]
    )
    assert result == 0
    assert m.read_bytes() == before
    assert "skip: DASC publication decision is not approved" in capsys.readouterr().out
