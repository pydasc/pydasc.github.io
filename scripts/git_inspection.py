"""Read-only, bounded local Git object inspection."""

import subprocess
from pathlib import Path, PurePosixPath
from publication_errors import CollectionError


def inspect_git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=not binary, timeout=60
        )
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise CollectionError(f"git inspection failed in {repo.name}") from exc
    return result.stdout


def object_kind(repo: Path, commit: str, path: PurePosixPath) -> str | None:
    """Return the safe Git object type for an exact path at an exact commit."""
    raw = inspect_git(
        repo,
        "ls-tree",
        "-z",
        "--full-tree",
        commit,
        "--",
        path.as_posix(),
        binary=True,
    )
    assert isinstance(raw, bytes)
    expected = path.as_posix().encode("utf-8")
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, encoded_path = record.partition(b"\t")
        fields = metadata.split()
        if separator and encoded_path == expected and len(fields) == 3:
            mode, object_type, _ = fields
            if mode == b"120000" or object_type not in {b"blob", b"tree"}:
                return None
            return object_type.decode("ascii")
    return None
