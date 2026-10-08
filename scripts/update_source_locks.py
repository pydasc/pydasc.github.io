#!/usr/bin/env python3
"""Validate candidate source checkouts and update only manifest commit locks."""

from __future__ import annotations

import argparse
import os
import yaml
import subprocess
import sys
import tempfile
from pathlib import Path

from collect_docs import (
    CollectionError,
    EXPECTED,
    SHA_RE,
    UnapprovedPublicationError,
    _read_regular_file,
    load_manifest,
)


def _head(checkout: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CollectionError(f"cannot inspect candidate checkout: {checkout}") from exc
    if not SHA_RE.fullmatch(result):
        raise CollectionError(f"candidate checkout has invalid HEAD: {checkout}")
    return result


def _lock_nodes(text: str):
    """Locate scalar spans after the authoritative manifest validation."""

    def child(node, key):
        return next(value for name, value in node.value if name.value == key)

    root = yaml.compose(text, Loader=yaml.SafeLoader)
    sources = child(root, "sources")
    result = {}
    for source in EXPECTED:
        source_node = child(sources, source)
        value = child(source_node, "checkout_commit")
        if not (
            source_node.start_mark.index <= value.start_mark.index < source_node.end_mark.index
        ):
            raise CollectionError("aliased checkout locks cannot be edited safely")
        if value.style not in (None, "'", '"'):
            raise CollectionError("checkout lock must be a plain or quoted scalar")
        result[source] = value
    return result


def _replace_lock(text: str, source: str, commit: str) -> str:
    node = _lock_nodes(text)[source]
    # Anchors/tags are not part of the scalar value; preserve them by refusing
    # ambiguous editing rather than silently changing their dependents.
    raw = text[node.start_mark.index : node.end_mark.index]
    quote = node.style or ""
    if raw != quote + node.value + quote:
        raise CollectionError("checkout lock has unsupported anchors, tags or escapes")
    return text[: node.start_mark.index] + quote + commit + quote + text[node.end_mark.index :]


def _replace_manifest(manifest: Path, target: Path, original: bytes, identity, candidate: str):
    lock = target.parent / f".{target.name}.update-lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise CollectionError("manifest update already active or interrupted") from exc
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".manifest-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(candidate.encode("utf-8"))
            stream.flush()
            os.fchmod(stream.fileno(), identity.st_mode & 0o777)
            os.fsync(stream.fileno())
        current = target.lstat()
        if (
            manifest.resolve() != target
            or (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino)
            or _read_regular_file(target, "website manifest") != original
        ):
            raise CollectionError("website manifest changed during candidate validation")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.rmdir()


def update(manifest: Path, checkouts: dict[str, Path]) -> dict[str, tuple[str, str]]:
    # Validate the current file fully before deriving any candidate document.
    load_manifest(manifest)
    target = manifest.resolve()
    identity = target.stat()
    original_bytes = _read_regular_file(target, "website manifest")
    original = original_bytes.decode("utf-8")
    nodes = _lock_nodes(original)
    candidate = original
    changes: dict[str, tuple[str, str]] = {}
    for name in EXPECTED:
        current = nodes[name].value
        proposed = _head(checkouts[name])
        candidate = _replace_lock(candidate, name, proposed)
        if current != proposed:
            changes[name] = (current, proposed)

    # Validate source identities, contracts, approvals, rights, and selected files
    # against the complete candidate before changing the publication boundary.
    with tempfile.TemporaryDirectory(prefix="dasc-lock-update-") as temporary:
        candidate_path = Path(temporary) / "docs-manifest.yml"
        candidate_path.write_text(candidate, encoding="utf-8")
        load_manifest(candidate_path, checkouts)
    if changes:
        _replace_manifest(manifest, target, original_bytes, identity, candidate)
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pydasc", type=Path, required=True)
    parser.add_argument("--dasc", type=Path, required=True)
    parser.add_argument(
        "--skip-unapproved",
        action="store_true",
        help="exit successfully without changing locks when a candidate contract is not approved",
    )
    args = parser.parse_args(argv)
    try:
        changes = update(
            args.manifest,
            {"pydasc": args.pydasc.resolve(), "dasc": args.dasc.resolve()},
        )
    except UnapprovedPublicationError as exc:
        if args.skip_unapproved:
            print(f"skip: {exc}")
            return 0
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (CollectionError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for name, (old, new) in sorted(changes.items()):
        print(f"{name}: {old} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
