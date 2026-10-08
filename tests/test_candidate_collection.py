import json
import pytest
from source_fixtures import fixture, git, hashes
from publication_errors import CollectionError
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
