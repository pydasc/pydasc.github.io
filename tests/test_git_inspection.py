import subprocess
from types import SimpleNamespace
import pytest
from publication_errors import CollectionError
from git_inspection import inspect_git


@pytest.mark.parametrize("binary", [True, False])
def test_git_inspection_is_bounded_and_preserves_output_type(tmp_path, monkeypatch, binary):
    value = b"object" if binary else "object"

    def result(args, **kwargs):
        assert kwargs["timeout"] == 60
        assert kwargs["text"] is not binary
        assert kwargs["capture_output"] and kwargs["check"]
        return SimpleNamespace(stdout=value)

    monkeypatch.setattr(subprocess, "run", result)
    assert inspect_git(tmp_path, "show", "HEAD:README.md", binary=binary) == value


def test_git_timeout_has_controlled_error(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 60)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(CollectionError, match="git inspection failed"):
        inspect_git(tmp_path, "status")
