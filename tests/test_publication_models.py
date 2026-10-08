import pytest
from source_fixtures import fixture
from source_manifest import load_manifest, read_source_locks, approve_entries
from publication_models import ApprovedEntry, SelectedEntry, InventoryRecord
from publication_errors import CollectionError


def test_selection_carries_no_fabricated_approval(tmp_path):
    manifest, pydasc, dasc = fixture(tmp_path)
    selections = load_manifest(manifest)
    assert all(type(item) is SelectedEntry for item in selections)
    assert all(not hasattr(item, "content_commit") for item in selections)
    with pytest.raises(CollectionError, match="approved entry"):
        InventoryRecord.from_approved(selections[0], b"unapproved")
    entries = approve_entries(read_source_locks(manifest), {"pydasc": pydasc, "dasc": dasc})
    assert all(type(item) is ApprovedEntry and item.content_commit != "0" * 40 for item in entries)


def test_assembly_refuses_syntax_only_entries(tmp_path, monkeypatch):
    import collect_docs

    manifest, pydasc, dasc = fixture(tmp_path)
    selections = load_manifest(manifest)
    monkeypatch.setattr(collect_docs, "load_manifest", lambda *args: selections)
    with pytest.raises(CollectionError, match="requires approved entries"):
        collect_docs.assemble(manifest, tmp_path / "out", pydasc, dasc)
