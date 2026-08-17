#!/usr/bin/env python3
"""Validate candidate source checkouts and update only manifest commit locks."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from collect_docs import (
    CollectionError,
    EXPECTED,
    SHA_RE,
    UnapprovedPublicationError,
    load_manifest,
)


def _head(checkout: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=checkout, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CollectionError(f"cannot inspect candidate checkout: {checkout}") from exc
    if not SHA_RE.fullmatch(result):
        raise CollectionError(f"candidate checkout has invalid HEAD: {checkout}")
    return result


def _replace_lock(text: str, source: str, commit: str) -> str:
    pattern = re.compile(
        rf"(?ms)^(  {re.escape(source)}:\n(?:(?!^  [a-z]).*?))"
        r"^(    checkout_commit: )[0-9a-f]{40}$"
    )
    updated, count = pattern.subn(rf"\g<1>\g<2>{commit}", text)
    if count != 1:
        raise CollectionError(f"cannot locate unique checkout lock for {source}")
    return updated


def update(manifest: Path, checkouts: dict[str, Path]) -> dict[str, tuple[str, str]]:
    # Validate the current file fully before deriving any candidate document.
    load_manifest(manifest)
    original = manifest.read_text(encoding="utf-8")
    candidate = original
    changes: dict[str, tuple[str, str]] = {}
    for name in EXPECTED:
        current_match = re.search(
            rf"(?ms)^  {re.escape(name)}:\n(?:(?!^  [a-z]).)*?^    checkout_commit: ([0-9a-f]{{40}})$",
            original,
        )
        if current_match is None:
            raise CollectionError(f"cannot read checkout lock for {name}")
        current = current_match.group(1)
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
        manifest.write_text(candidate, encoding="utf-8")
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
