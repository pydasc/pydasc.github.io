"""Descriptor-checked reads and filesystem identity boundaries."""

import os
import stat
from pathlib import Path, PurePosixPath
from contextlib import contextmanager
from typing import BinaryIO, Iterator
from publication_errors import CollectionError
from publication_policy import MAX_FILE_BYTES


@contextmanager
def open_regular_file(path: Path, context: str) -> Iterator[BinaryIO]:
    """Open a regular file without following a swapped symlink or FIFO.

    Check the directory entry before opening, then compare the opened file's
    identity with both the original and current entries before reading bytes.
    O_NONBLOCK prevents a replacement FIFO from blocking in open().
    """
    try:
        initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise CollectionError(f"unsafe {context}: expected a regular file: {path}")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            current = path.lstat()
            identity = (opened.st_dev, opened.st_ino)
            if (
                not stat.S_ISREG(opened.st_mode)
                or not stat.S_ISREG(current.st_mode)
                or identity != (initial.st_dev, initial.st_ino)
                or identity != (current.st_dev, current.st_ino)
            ):
                raise CollectionError(f"unsafe {context}: file changed while opening: {path}")
            yield stream
    except (OSError, ValueError) as exc:
        if isinstance(exc, CollectionError):
            raise
        raise CollectionError(f"cannot read {context}: {path}") from exc


def read_regular_file(path: Path, context: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    """Read publication input bytes with a strict size limit."""
    with open_regular_file(path, context) as stream:
        if os.fstat(stream.fileno()).st_size > max_bytes:
            raise CollectionError(f"oversized {context}: {path}")
        data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise CollectionError(f"oversized {context}: {path}")
        return data


def check_inventory_path(path: Path, *, required: bool = False) -> None:
    """Inspect the directory entry itself, including dangling symlinks."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if required:
            raise CollectionError(f"missing inventory: {path}")
        return
    if not stat.S_ISREG(mode):
        raise CollectionError(f"unsafe inventory path (expected a regular file): {path}")


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def filesystem_inside(path: Path, root: Path) -> bool:
    """Include filesystem aliases without assuming case-insensitive names.

    resolve() removes symlinks but preserves spelling on case-insensitive
    filesystems. Compare identities of existing ancestors as well, so even a
    not-yet-created destination beneath an alias of root is contained.
    Inspection errors other than missing paths must propagate to the caller.
    """
    if inside(path, root):
        return True
    try:
        root_stat = root.stat()
    except FileNotFoundError:
        return False
    identity = (root_stat.st_dev, root_stat.st_ino)
    for ancestor in (path, *path.parents):
        try:
            ancestor_stat = ancestor.stat()
        except FileNotFoundError:
            continue
        if (ancestor_stat.st_dev, ancestor_stat.st_ino) == identity:
            return True
    return False


def relative_path(value: object, context: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "`" in value
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise CollectionError(f"{context} must be a non-empty POSIX path")
    result = PurePosixPath(value)
    if (
        not result.parts
        or result.is_absolute()
        or any(part in {"", ".", ".."} for part in result.parts)
        or any(c in value for c in "*?[")
    ):
        raise CollectionError(f"unsafe {context}: {value!r}")
    return result
