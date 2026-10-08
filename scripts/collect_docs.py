#!/usr/bin/env python3
"""Assemble approved documentation from exact local source checkouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterator
from urllib.parse import SplitResult, quote, unquote_to_bytes, urlsplit

import markdown
import yaml

from source_manifest import load_manifest, _source_contract
from publication_models import (
    ApprovedEntry as Entry,
    ApprovedEntry,
    InventoryRecord,
    provenance_banner,
)
from markdown_policy import (
    MarkdownHTMLGuard,
    RenderedReferenceParser,
    RenderedHTMLGuard,
    _validate_markdown_html,
    MarkdownLink,
    _decode_link_path,
    _split_link,
    _validate_rendered_url,
    _markdown_visible_text,
    _markdown_link_matches,
    _has_reference_definition,
    _rewrite,
)
from html_policy import unique_attributes

from publication_errors import CollectionError, UnapprovedPublicationError
from publication_policy import (
    EXPECTED,
    LEGACY_CONTRACT_REPOSITORIES,
    ALLOWED,
    MEDIA,
    MAX_FILE_BYTES,
    SHA_RE,
    SPDX_RE,
    DOCUMENTATION_STATUSES,
    MARKDOWN_AUTOLINK_RE,
    BLOCKQUOTE_PREFIX_RE,
    LIST_PREFIX_RE,
    HTML_TAG_START_RE,
    ACTIVE_HTML_TAGS,
    UNSAFE_HTML_ATTRIBUTES,
    UNSAFE_ATTRIBUTION_RE,
    FORBIDDEN,
    MARKDOWN_POLICY_EXTENSIONS,
    RENDER_ALLOWED_ATTRIBUTES,
    RENDER_FORBIDDEN_TAGS,
)
from safe_files import (
    open_regular_file as _open_regular_file,
    check_inventory_path as _check_inventory_path,
    inside as _inside,
    filesystem_inside as _filesystem_inside,
    relative_path as _path,
)
from safe_files import read_regular_file
from structured_input import (
    UniqueKeyLoader as _ManifestLoader,
    unique_json_object as _json_object,
    read_json as _read_json,
    read_yaml as _read_yaml,
    require_mapping as _mapping,
)
from git_inspection import inspect_git as _git, object_kind as _git_object_kind

from publication_transaction import publish, PublicationTransactionError

# Repository transfers preserve history, but the source repositories currently
# publish contracts bearing their former URLs. Accept only these exact aliases;
# the website manifest and fetch workflows still require the canonical org URLs.


# Extensions such as attr_list can attach arbitrary attributes to almost any
# rendered element. Only these (tag, attribute) pairs are how the site's own
# link/image syntax legitimately reaches the DOM; every other unsafe
# attribute or active element in the rendered output is rejected outright.


def _tree_state(repo: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    files = []
    listed = _git(repo, "ls-files", "-z", "-co", "--exclude-standard", binary=True)
    assert isinstance(listed, bytes)
    for encoded in listed.split(b"\0"):
        if not encoded:
            continue
        raw = os.fsdecode(encoded)
        path = repo / raw
        if path.is_file() and not path.is_symlink():
            # Unpublished upstream files can exceed the publication size limit;
            # hash them in bounded chunks, using the same safe opening policy.
            with _open_regular_file(path, "source integrity input") as stream:
                files.append((raw, hashlib.file_digest(stream, "sha256").hexdigest()))
    return status, tuple(files)


def _preflight_output(output: Path, checkouts: dict[str, Path], manifest: Path) -> Path:
    """Validate every publication target without creating or removing anything."""
    try:
        if output.is_symlink():
            raise CollectionError(f"unsafe output directory: {output}")
        output = output.resolve()
        if output.exists() and not output.is_dir():
            raise CollectionError(f"unsafe output directory: {output}")
        for name, checkout in checkouts.items():
            if _filesystem_inside(output, checkout) or _filesystem_inside(checkout, output):
                raise CollectionError(f"output overlaps {name} source checkout: {output}")
        # Protect both the directory entry used as input and its resolved target.
        manifest_paths = {manifest.parent.resolve() / manifest.name, manifest.resolve()}
        for name in EXPECTED:
            target = output / name
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise CollectionError(f"unsafe generated namespace: {target}")
            if any(_filesystem_inside(path, target) for path in manifest_paths):
                raise CollectionError(f"output would replace the input manifest: {manifest}")
        inventory = output / "generated-inventory.json"
        if any(_filesystem_inside(path, inventory) for path in manifest_paths):
            raise CollectionError(f"output would replace the input manifest: {manifest}")
        _check_inventory_path(inventory)
    except (OSError, RuntimeError) as exc:
        raise CollectionError(f"cannot inspect output paths: {output}") from exc
    return output


def _write_inventory_atomic(path: Path, inventory: list[dict[str, Any]]) -> None:
    """Replace the inventory entry; never truncate its existing inode/target."""
    _check_inventory_path(path)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=".generated-inventory-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(
                json.dumps({"schema_version": 1, "files": inventory}, indent=2, sort_keys=True)
                + "\n"
            )
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        _check_inventory_path(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def assemble(manifest: Path, output: Path, pydasc: Path, dasc: Path) -> list[dict[str, Any]]:
    try:
        checkouts = {"pydasc": pydasc.resolve(), "dasc": dasc.resolve()}
    except (OSError, RuntimeError) as exc:
        raise CollectionError("cannot resolve source checkout paths") from exc
    output = _preflight_output(output, checkouts, manifest)
    before = {name: _tree_state(repo) for name, repo in checkouts.items()}
    entries = load_manifest(manifest, checkouts)
    if any(not isinstance(entry, ApprovedEntry) for entry in entries):
        raise CollectionError("assembly requires approved entries")
    selected = {(entry.source_name, entry.source.as_posix()): entry for entry in entries}
    inventory: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dasc-assembly-") as temporary:
        stage = Path(temporary) / "docs"
        for entry in entries:
            root = checkouts[entry.source_name]
            source = root.joinpath(*entry.source.parts)
            if (
                source.is_symlink()
                or not _inside(source.resolve(strict=False), root)
                or not source.is_file()
            ):
                raise CollectionError(f"unsafe or missing source: {entry.source}")
            if source.stat().st_size > MAX_FILE_BYTES:
                raise CollectionError(f"oversized source: {entry.source}")
            if _git_object_kind(root, entry.content_commit, entry.source) != "blob":
                raise CollectionError(f"source is not a regular Git blob: {entry.source}")
            committed = _git(
                root, "show", f"{entry.content_commit}:{entry.source.as_posix()}", binary=True
            )
            data = _read_regular_file(source, "source document")
            if data != committed:
                raise CollectionError(f"source differs from approved commit: {entry.source}")
            destination = stage.joinpath(*entry.destination.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if entry.source.suffix.lower() == ".md":
                try:
                    body = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                except UnicodeDecodeError as exc:
                    raise CollectionError(f"non-UTF-8 Markdown: {entry.source}") from exc
                if FORBIDDEN.search(body):
                    raise CollectionError(f"credential-like or local content: {entry.source}")
                _validate_markdown_html(_markdown_visible_text(body), entry.source)
                if _has_reference_definition(body):
                    raise CollectionError(f"reference-style links are not allowed: {entry.source}")
                body = _rewrite(body, entry, selected, root)
                encoded_source = quote(entry.source.as_posix(), safe="/")
                source_url = f"{entry.repository}/blob/{entry.content_commit}/{encoded_source}"
                project = "PyDASC" if entry.source_name == "pydasc" else "DASC"
                banner = (
                    provenance_banner(
                        {
                            "repository": entry.repository,
                            "commit": entry.content_commit,
                            "source": entry.source.as_posix(),
                            "status": entry.status,
                            "license": entry.license_id,
                            "attribution": entry.attribution,
                        }
                    )
                    + "\n"
                )
                attribution = (
                    f"    **Attribution:** {entry.attribution}  \n" if entry.attribution else ""
                )
                publication = (
                    '!!! info "Publication record"\n'
                    f"    **Project:** {project} · **Status:** {entry.status} · **License:** `{entry.license_id}`  \n"
                    f"{attribution}"
                    f"    **Immutable revision:** [`{entry.content_commit}`]({source_url}) · "
                    f"**Source path:** `{entry.source.as_posix()}`\n\n"
                )
                data = (banner + publication + body.rstrip() + "\n").encode()
            destination.write_bytes(data)
            inventory.append(InventoryRecord.from_approved(entry, data).mapping())
        # Recheck the entire boundary after staging, before touching any output.
        _preflight_output(output, checkouts, manifest)
        if before != {name: _tree_state(repo) for name, repo in checkouts.items()}:
            raise CollectionError("source checkout changed during assembly")
        inventory.sort(key=lambda item: item["destination"])
        try:
            publish(
                output,
                stage,
                tuple(EXPECTED),
                lambda: _write_inventory_atomic(output / "generated-inventory.json", inventory),
                lambda: _preflight_output(output, checkouts, manifest),
            )
        except PublicationTransactionError as exc:
            raise CollectionError(str(exc)) from exc

    after = {name: _tree_state(repo) for name, repo in checkouts.items()}
    if before != after:
        raise CollectionError("source checkout changed during assembly")
    return inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pydasc", type=Path, required=True)
    parser.add_argument("--dasc", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        assemble(args.manifest, args.output, args.pydasc, args.dasc)
    except (CollectionError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


# Compatibility adapter keeps the historical configurable byte-limit seam.
def _read_regular_file(path: Path, context: str) -> bytes:
    return read_regular_file(path, context, max_bytes=MAX_FILE_BYTES)


if __name__ == "__main__":
    raise SystemExit(main())
