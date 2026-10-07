#!/usr/bin/env python3
"""Check a complete documentation release using already-fetched local sources."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Iterator

from collect_docs import (
    EXPECTED,
    CollectionError,
    _filesystem_inside,
    _read_regular_file,
    assemble,
)
from validate_accessibility import validate as validate_accessibility
from validate_docs import validate as validate_docs
from validate_physics_docs import validate as validate_physics
from validate_site import validate as validate_site


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ARTIFACT = re.compile(
    rb"(github_pat_|ghp_[A-Za-z0-9]{20,}|"
    rb"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"/(Users|home)/[^\s<]+|"
    rb"https?://(localhost|127\.0\.0\.1|[^/\s]+\.internal))"
)


def _tree_entries(root: Path) -> Iterator[tuple[Path, bool]]:
    """Walk regular files/directories without following symlinks or hiding errors."""
    if root.is_symlink() or not root.is_dir():
        raise CollectionError(f"missing/unsafe release directory: {root}")
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as children:
            for child in children:
                path = Path(child.path)
                mode = child.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    yield path, True
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    yield path, False
                else:
                    raise CollectionError(f"unsafe release entry: {path}")


def snapshot_generated(docs: Path) -> dict[str, str | None]:
    """Fingerprint the complete generated tree, including empty directories."""
    inventory = docs / "generated-inventory.json"
    snapshot: dict[str, str | None] = {
        inventory.name: hashlib.sha256(
            _read_regular_file(inventory, "inventory")
        ).hexdigest()
    }
    for namespace in EXPECTED:
        for path, is_directory in _tree_entries(docs / namespace):
            snapshot[path.relative_to(docs).as_posix()] = (
                None
                if is_directory
                else hashlib.sha256(
                    _read_regular_file(path, "generated document")
                ).hexdigest()
            )
    return snapshot


def scan_artifact(site: Path) -> None:
    """Reject unsafe files and forbidden content without printing matched bytes."""
    for path, is_directory in _tree_entries(site):
        if not is_directory:
            data = _read_regular_file(path, "site artifact")
            if FORBIDDEN_ARTIFACT.search(data):
                raise CollectionError(
                    f"forbidden credential-like or private/local content: "
                    f"{path.relative_to(site)}"
                )


def check_release(root: Path, pydasc: Path, dasc: Path) -> None:
    """Apply every release gate; fetching, tests and deployment stay in CI."""
    root, pydasc, dasc = root.resolve(), pydasc.resolve(), dasc.resolve()
    manifest, docs, site = root / "docs-manifest.yml", root / "docs", root / "site"
    if site.is_symlink():
        raise CollectionError(f"unsafe site output directory: {site}")
    for source in (pydasc, dasc):
        if _filesystem_inside(site, source) or _filesystem_inside(source, site):
            raise CollectionError("site output overlaps a source checkout")

    print("Collect and validate approved documents", flush=True)
    assemble(manifest, docs, pydasc, dasc)
    validate_docs(manifest, docs)
    validate_physics(docs)

    print("Verify deterministic assembly", flush=True)
    before = snapshot_generated(docs)
    assemble(manifest, docs, pydasc, dasc)
    if before != snapshot_generated(docs):
        raise CollectionError("generated documentation differs between collections")
    validate_docs(manifest, docs)

    print("Build strict site", flush=True)
    subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict"], cwd=root, check=True
    )
    print("Validate site links, accessibility and complete artifact", flush=True)
    validate_site(site, docs / "stylesheets/readthedocs.css")
    validate_accessibility(site)
    scan_artifact(site)
    print("Release checks passed", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pydasc", type=Path, required=True)
    parser.add_argument("--dasc", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        check_release(ROOT, args.pydasc, args.dasc)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
