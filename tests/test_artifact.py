from pathlib import Path
import sys
import os
import pytest

from validate_artifact import validate, main


@pytest.mark.parametrize("location", ["index.html", "assets/data.bin", "pydasc/index.html"])
@pytest.mark.parametrize(
    "payload",
    [
        "AKIA" + "A" * 16,
        "github_pat_" + "synthetic",
        "ghp_" + "synthetic",
        "https://localhost/private",
    ],
)
def test_artifact_scans_all_assets_without_echoing_payload(tmp_path, capsys, location, payload):
    path = tmp_path / location
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff" + payload.encode())
    assert main(["--site", str(tmp_path)]) == 1
    message = capsys.readouterr().err
    assert "artifact.forbidden-content" in message
    assert location in message
    assert payload not in message


@pytest.mark.parametrize("kind", ["symlink", "fifo", "oversize"])
def test_artifact_rejects_unsafe_entries(tmp_path, kind):
    path = tmp_path / "entry"
    if kind == "symlink":
        path.symlink_to(tmp_path / "missing")
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        with path.open("wb") as stream:
            stream.truncate(5 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="artifact"):
        validate(tmp_path)


def test_artifact_accepts_regular_text_and_binary(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Public</h1>")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\xff")
    validate(tmp_path)
