from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import pytest, yaml

import collect_docs
from collect_docs import (
    MARKDOWN_POLICY_EXTENSIONS,
    CollectionError,
    assemble,
    load_manifest,
)
from validate_docs import validate
from update_source_locks import main as update_source_locks_main
from update_source_locks import update as update_source_locks


from source_fixtures import git, repo, fixture, hashes


def test_source_lock_update_validates_candidate_and_changes_only_commit(tmp_path):
    m, p, d = fixture(tmp_path)
    before = yaml.safe_load(m.read_text())
    (p / "CHANGELOG.md").write_text("candidate\n")
    git(p, "add", "CHANGELOG.md")
    git(p, "commit", "-qm", "candidate")
    changes = update_source_locks(m, {"pydasc": p, "dasc": d})
    after = yaml.safe_load(m.read_text())
    assert changes == {
        "pydasc": (before["sources"]["pydasc"]["checkout_commit"], git(p, "rev-parse", "HEAD"))
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
    changes = update_source_locks(m, {"pydasc": p, "dasc": d})
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
    rejected = update_source_locks_main(
        ["--manifest", str(m), "--pydasc", str(p), "--dasc", str(d)]
    )
    assert rejected == 1
    assert m.read_bytes() == before
    assert "error: DASC publication decision is not approved" in capsys.readouterr().err
    result = update_source_locks_main(
        ["--skip-unapproved", "--manifest", str(m), "--pydasc", str(p), "--dasc", str(d)]
    )
    assert result == 0
    assert m.read_bytes() == before
    assert "skip: DASC publication decision is not approved" in capsys.readouterr().out


@pytest.mark.parametrize("quote", ["'", '"'])
def test_lock_updates_preserve_quotes_comments_and_indentation(tmp_path, quote):
    import re

    manifest, pydasc, dasc = fixture(tmp_path)
    text = manifest.read_text()
    text = re.sub(
        r"(checkout_commit: )([0-9a-f]{40})",
        lambda m: m[1] + quote + m[2] + quote + " # reviewed",
        text,
    )
    text = "# Retain this comment\n" + text
    manifest.write_text(text)
    old = git(pydasc, "rev-parse", "HEAD")
    (pydasc / "new.txt").write_text("candidate")
    git(pydasc, "add", ".")
    git(pydasc, "commit", "-qm", "candidate")
    new = git(pydasc, "rev-parse", "HEAD")
    update_source_locks(manifest, {"pydasc": pydasc, "dasc": dasc})
    assert manifest.read_text() == text.replace(old, new)


@pytest.mark.parametrize("failure", ["replace", "concurrent"])
def test_manifest_replacement_failure_preserves_file(tmp_path, monkeypatch, failure):
    import update_source_locks as updater

    manifest = tmp_path / "manifest.yml"
    manifest.write_text("old")
    identity = manifest.stat()
    if failure == "replace":

        def fail(*args):
            raise OSError("injected replace failure")

        monkeypatch.setattr(updater.os, "replace", fail)
        error = OSError
        expected = "old"
    else:

        def concurrent(fd):
            manifest.write_text("operator change")

        monkeypatch.setattr(updater.os, "fsync", concurrent)
        error = CollectionError
        expected = "operator change"
    with pytest.raises(error):
        updater._replace_manifest(manifest, manifest, b"old", identity, "new")
    assert manifest.read_text() == expected
    assert not list(tmp_path.glob(".manifest-*"))
    assert not list(tmp_path.glob("*.update-lock"))
