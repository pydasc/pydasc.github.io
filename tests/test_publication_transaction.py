from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import publication_transaction as transaction


def setup(tmp):
    output, stage = tmp / "docs", tmp / "stage"
    for root, text in [(output, "old"), (stage, "new")]:
        for name in ("pydasc", "dasc"):
            (root / name).mkdir(parents=True)
            (root / name / "index.md").write_text(text)
    (output / "generated-inventory.json").write_text("old inventory")
    (output / "authored.md").write_text("authored")
    return output, stage


def snapshot(output):
    return {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}


@pytest.mark.parametrize("failure", ["prepare", "backup", "install", "inventory"])
def test_transaction_failure_restores_previous_generation(tmp_path, monkeypatch, failure):
    output, stage = setup(tmp_path)
    before = snapshot(output)
    replace = transaction.os.replace
    copy = transaction.shutil.copytree
    fired = False
    def fail_replace(src, dst):
        nonlocal fired
        phase = "backup" if Path(dst).parent.name == "previous" else "install"
        if not fired and failure == phase and Path(src).name == "dasc":
            fired = True
            raise OSError("injected replacement failure")
        return replace(src, dst)
    def fail_copy(src, dst, *args, **kwargs):
        if failure == "prepare" and Path(src).name == "dasc":
            raise OSError("injected preparation failure")
        return copy(src, dst, *args, **kwargs)
    def write_inventory():
        (output / "generated-inventory.json").write_text("new inventory")
        if failure == "inventory":
            raise OSError("injected inventory failure")
    monkeypatch.setattr(transaction.os, "replace", fail_replace)
    monkeypatch.setattr(transaction.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="injected"):
        transaction.publish(output, stage, ("pydasc", "dasc"), write_inventory, lambda: None)
    assert snapshot(output) == before
    assert not (tmp_path / ".docs.collection-lock").exists()


def test_transaction_rejects_a_concurrent_writer(tmp_path):
    output, stage = setup(tmp_path)
    def while_locked():
        with pytest.raises(transaction.PublicationTransactionError, match="active or needs recovery"):
            transaction.publish(output, stage, ("pydasc", "dasc"), lambda:None, lambda:None)
    transaction.publish(output, stage, ("pydasc", "dasc"),
                        lambda:(output / "generated-inventory.json").write_text("new inventory"), while_locked)
    assert (output / "pydasc/index.md").read_text() == "new"
    assert (output / "dasc/index.md").read_text() == "new"
    assert (output / "authored.md").read_text() == "authored"


def test_preflight_failure_does_not_change_output(tmp_path):
    output, stage = setup(tmp_path)
    before = snapshot(output)
    def reject():
        raise ValueError("unsafe output")
    with pytest.raises(ValueError, match="unsafe output"):
        transaction.publish(output, stage, ("pydasc", "dasc"), lambda:None, reject)
    assert snapshot(output) == before
