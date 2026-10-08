"""Real local Git transport exercises acquisition without network credentials."""

import os
import subprocess
import pytest
from source_fixtures import fixture, git
import acquire_sources
from publication_errors import CollectionError


@pytest.mark.parametrize("mode", ["reviewed", "candidate"])
def test_source_acquisition_uses_explicit_refs_and_ephemeral_auth(tmp_path, monkeypatch, mode):
    manifest, pydasc, dasc = fixture(tmp_path)
    sources = {"https://github.com/pydasc/pydasc": pydasc, "https://github.com/pydasc/dasc": dasc}
    original = subprocess.run
    calls = []

    def local_transport(args, **kwargs):
        calls.append(list(args))
        environment = kwargs.get("env", {})
        if args[:4] == ["git", "remote", "add", "origin"]:
            assert args[-1] in sources
            assert environment["GIT_CONFIG_VALUE_0"] == ""
            assert environment["GIT_CONFIG_VALUE_1"] == os.devnull
            assert "AUTHORIZATION: basic " in environment["GIT_CONFIG_VALUE_2"]
            args = [*args[:-1], str(sources[args[-1]])]
        return original(args, **kwargs)

    monkeypatch.setattr(acquire_sources.subprocess, "run", local_transport)
    output = tmp_path / "checkouts"
    result = acquire_sources.acquire(manifest, output, mode, "synthetic-token")
    assert set(result) == {"pydasc", "dasc"}
    for name, source in [("pydasc", pydasc), ("dasc", dasc)]:
        assert git(result[name], "rev-parse", "HEAD") == git(source, "rev-parse", "HEAD")
        config = (result[name] / ".git/config").read_text()
        assert "synthetic-token" not in config and "AUTHORIZATION" not in config
    fetched = [args[-1] for args in calls if args[:2] == ["git", "fetch"]]
    assert ("HEAD" in fetched) is (mode == "candidate")
    with pytest.raises(CollectionError, match="fresh"):
        acquire_sources.acquire(manifest, output, mode, "synthetic-token")


def test_acquisition_rejects_invalid_mode_and_docs_destination(tmp_path):
    manifest, _, _ = fixture(tmp_path)
    with pytest.raises(CollectionError, match="mode"):
        acquire_sources.acquire(manifest, tmp_path / "out", "latest", "synthetic")
    with pytest.raises(CollectionError, match="outside docs"):
        acquire_sources.acquire(manifest, tmp_path / "docs/checkouts", "reviewed", "synthetic")


def test_acquisition_errors_do_not_echo_transport_payload(tmp_path, monkeypatch, capsys):
    manifest, _, _ = fixture(tmp_path)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="synthetic-private-payload")

    monkeypatch.setattr(acquire_sources.subprocess, "run", fail)
    monkeypatch.setenv("SOURCE_TOKEN", "synthetic-token")
    assert (
        acquire_sources.main(
            ["--manifest", str(manifest), "--output", str(tmp_path / "out"), "--mode", "reviewed"]
        )
        == 1
    )
    error = capsys.readouterr().err
    assert "source acquisition failed" in error
    assert "synthetic-private-payload" not in error and "synthetic-token" not in error
