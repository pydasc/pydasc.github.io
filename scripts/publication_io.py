"""Guarded publication reads and filesystem boundary checks.

read_regular_file bounds bytes; read_manifest_yaml uses that reader and permits
an explicitly resolved website-manifest symlink. read_json parses supplied bytes
without duplicate keys; callers acquire file bytes through the bounded reader.
open_regular_file checks identity and type without limiting the stream size,
for chunked hashing of unpublished source files by the collector.
"""

from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator

import yaml

from publication_policy import CollectionError

__all__ = [
    "MAX_FILE_BYTES",
    "open_regular_file",
    "read_regular_file",
    "read_json",
    "read_manifest_yaml",
    "path_inside",
    "check_inventory_path",
    "filesystem_inside",
]

MAX_FILE_BYTES = 5 * 1024 * 1024


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
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
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
                raise CollectionError(
                    f"unsafe {context}: file changed while opening: {path}"
                )
            yield stream
    except (OSError, ValueError) as exc:
        if isinstance(exc, CollectionError):
            raise
        raise CollectionError(f"cannot read {context}: {path}") from exc


def read_regular_file(path: Path, context: str) -> bytes:
    """Read publication input bytes with a strict size limit."""
    with open_regular_file(path, context) as stream:
        if os.fstat(stream.fileno()).st_size > MAX_FILE_BYTES:
            raise CollectionError(f"oversized {context}: {path}")
        data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise CollectionError(f"oversized {context}: {path}")
        return data


class _ManifestLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently changing a publication decision."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise CollectionError("manifest keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CollectionError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def read_json(data: bytes, context: str) -> Any:
    try:
        return json.loads(data, object_pairs_hook=_json_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CollectionError(f"invalid {context}: {exc}") from exc


def read_manifest_yaml(path: Path) -> dict[str, Any]:
    try:
        # Website manifests may be explicitly addressed through a symlink;
        # source contracts and generated files must not be symlinks.
        data = read_regular_file(path.resolve(), "website manifest")
        return yaml.load(data.decode("utf-8"), Loader=_ManifestLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError, RuntimeError) as exc:
        raise CollectionError(f"cannot read website manifest: {exc}") from exc


def path_inside(path: Path, root: Path) -> bool:
    """Check lexical containment; callers resolve paths before trusting it."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def check_inventory_path(path: Path, *, required: bool = False) -> None:
    """Inspect the directory entry itself, including dangling symlinks."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if required:
            raise CollectionError(f"missing inventory: {path}")
        return
    if not stat.S_ISREG(mode):
        raise CollectionError(
            f"unsafe inventory path (expected a regular file): {path}"
        )


def filesystem_inside(path: Path, root: Path) -> bool:
    """Include filesystem aliases without assuming case-insensitive names.

    resolve() removes symlinks but preserves spelling on case-insensitive
    filesystems. Compare identities of existing ancestors as well, so even a
    not-yet-created destination beneath an alias of root is contained.
    Inspection errors other than missing paths must propagate to the caller.
    """
    if path_inside(path, root):
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
