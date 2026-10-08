#!/usr/bin/env python3
"""Scan every final artifact file without echoing potentially private payloads."""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import stat
import sys
from collect_docs import FORBIDDEN, MAX_FILE_BYTES, _read_regular_file


def validate(site: Path) -> None:
    if site.is_symlink() or not site.is_dir():
        raise ValueError("artifact root must be a real directory")
    site = site.resolve(strict=True)
    pending = [site]
    count = 0
    while pending:
        with os.scandir(pending.pop()) as children:
            entries = sorted(children, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(site)
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                pending.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise ValueError(f"artifact.nonregular: {relative}")
            if entry.stat(follow_symlinks=False).st_size > MAX_FILE_BYTES:
                raise ValueError(f"artifact.oversize: {relative}")
            data = _read_regular_file(path, "artifact file")
            if FORBIDDEN.search(data.decode("utf-8", errors="replace")):
                raise ValueError(f"artifact.forbidden-content: {relative} (payload redacted)")
            count += 1
    if not count:
        raise ValueError("artifact.empty: no files")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate(args.site)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
