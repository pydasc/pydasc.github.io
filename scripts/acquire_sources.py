#!/usr/bin/env python3
"""Acquire fresh reviewed or candidate checkouts without persisting credentials."""

from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from publication_errors import CollectionError
from publication_policy import SHA_RE, MAX_FILE_BYTES
from safe_files import filesystem_inside
from structured_input import read_json
from source_manifest import read_source_locks, load_manifest


def git_environment(token: str) -> dict[str, str]:
    if not token:
        raise CollectionError("SOURCE_TOKEN is required for source acquisition")
    header = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{header}", flush=True)
    environment = dict(os.environ)
    environment.pop("GIT_CONFIG_PARAMETERS", None)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "3",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "core.hooksPath",
            "GIT_CONFIG_VALUE_1": os.devnull,
            "GIT_CONFIG_KEY_2": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_2": f"AUTHORIZATION: basic {header}",
        }
    )
    return environment


def acquire(manifest: Path, output: Path, mode: str, token: str) -> dict[str, Path]:
    if mode not in {"reviewed", "candidate"}:
        raise CollectionError("source acquisition mode must be reviewed or candidate")
    locks = read_source_locks(manifest)
    if output.is_symlink() or filesystem_inside(
        output.resolve(), manifest.resolve().parent / "docs"
    ):
        raise CollectionError("source checkouts must be outside docs and not a symlink")
    environment = git_environment(token)
    output.mkdir(parents=True, exist_ok=True)
    # Never reset or overwrite a developer's checkout, even on retry.
    if any((output / lock.name).exists() or (output / lock.name).is_symlink() for lock in locks):
        raise CollectionError("source destinations must be fresh; use a new checkout directory")
    checkouts = {}
    for lock in locks:
        directory = output / lock.name
        directory.mkdir()

        def git(*args, binary=False):
            try:
                result = subprocess.run(
                    ["git", *args],
                    cwd=directory,
                    env=environment,
                    check=True,
                    capture_output=True,
                    text=not binary,
                    timeout=180,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise CollectionError(
                    f"source acquisition failed for {lock.name}: {args[0]}"
                ) from exc
            return result.stdout

        git("init", "--quiet")
        git("remote", "add", "origin", lock.repository)
        ref = lock.checkout_commit if mode == "reviewed" else "HEAD"
        git("fetch", "--quiet", "--no-tags", "--depth=1", "origin", ref)
        git("checkout", "--quiet", "--detach", "FETCH_HEAD")
        head = git("rev-parse", "HEAD").strip()
        if not SHA_RE.fullmatch(head) or (mode == "reviewed" and head != lock.checkout_commit):
            raise CollectionError(f"source checkout mismatch for {lock.name}")
        raw = git("show", f"{head}:{lock.publication_manifest.as_posix()}", binary=True)
        if len(raw) > MAX_FILE_BYTES:
            raise CollectionError(f"oversized publication contract for {lock.name}")
        contract = read_json(raw, f"{lock.name} publication contract")
        content = contract.get("source_commit") if isinstance(contract, dict) else None
        if not isinstance(content, str) or not SHA_RE.fullmatch(content):
            raise CollectionError(f"invalid source_commit for {lock.name}")
        git("fetch", "--quiet", "--no-tags", "--depth=1", "origin", content)
        checkouts[lock.name] = directory
    if mode == "reviewed":
        load_manifest(manifest, checkouts)
    # Candidate approvals are intentionally evaluated by update_source_locks,
    # whose --skip-unapproved semantics distinguish no-release from bad input.
    return checkouts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("reviewed", "candidate"), required=True)
    args = parser.parse_args(argv)
    try:
        result = acquire(args.manifest, args.output, args.mode, os.environ.get("SOURCE_TOKEN", ""))
    except (CollectionError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({name: str(path) for name, path in result.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
