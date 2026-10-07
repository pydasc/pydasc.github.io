#!/usr/bin/env python3
"""Validate assembled docs and checksummed inventory."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
from html import unescape
from pathlib import Path, PurePosixPath
from typing import cast
from urllib.parse import quote

from collect_docs import (
    FORBIDDEN,
    _decode_link_path,
    _markdown_link_matches,
    _split_link,
    load_manifest,
)
from publication_io import (
    check_inventory_path,
    read_json,
    read_regular_file,
)
from publication_policy import (
    DOCUMENTATION_STATUSES,
    EXPECTED,
    SHA_RE,
    SPDX_RE,
    UNSAFE_ATTRIBUTION_RE,
    CollectionError,
    Entry,
    InventoryRecord,
)


def _load_inventory(
    docs: Path, selected: dict[str, Entry]
) -> dict[str, InventoryRecord]:
    """Read the bounded inventory and match its destinations to the manifest."""
    inventory_path = docs / "generated-inventory.json"
    check_inventory_path(inventory_path, required=True)
    inventory = read_json(read_regular_file(inventory_path, "inventory"), "inventory")
    if (
        not isinstance(inventory, dict)
        or set(inventory) != {"schema_version", "files"}
        or type(inventory["schema_version"]) is not int
        or inventory["schema_version"] != 1
        or not isinstance(inventory["files"], list)
    ):
        raise CollectionError("invalid inventory schema")
    required_item_keys = {
        "destination",
        "sha256",
        "repository",
        "source",
        "commit",
        "status",
        "license",
        "attribution",
    }
    expected: dict[str, InventoryRecord] = {}
    for index, item in enumerate(inventory["files"]):
        if not isinstance(item, dict) or set(item) != required_item_keys:
            raise CollectionError(f"invalid inventory item at index {index}")
        destination = item["destination"]
        if not isinstance(destination, str):
            raise CollectionError(f"invalid inventory destination at index {index}")
        expected[destination] = cast(InventoryRecord, item)
    if len(expected) != len(inventory["files"]):
        raise CollectionError("duplicate inventory destination")
    if set(expected) != set(selected):
        raise CollectionError(
            f"inventory differs from manifest: missing={sorted(set(selected) - set(expected))}, "
            f"unexpected={sorted(set(expected) - set(selected))}"
        )
    return expected


def _validate_tree(docs: Path, expected: dict[str, InventoryRecord]) -> None:
    """Inspect every generated entry before reading any document content."""
    actual: set[str] = set()
    for namespace in EXPECTED:
        root = docs / namespace
        if root.is_symlink() or not root.is_dir():
            raise CollectionError(f"missing/unsafe namespace: {namespace}")
        pending = [root]
        while pending:
            # scandir propagates inspection errors instead of silently skipping
            # inaccessible subtrees, as glob implementations can do.
            with os.scandir(pending.pop()) as children:
                for child in children:
                    path = Path(child.path)
                    mode = child.stat(follow_symlinks=False).st_mode
                    if stat.S_ISLNK(mode):
                        raise CollectionError(f"output symlink: {path}")
                    if stat.S_ISDIR(mode):
                        pending.append(path)
                    elif stat.S_ISREG(mode):
                        actual.add(path.relative_to(docs).as_posix())
                    else:
                        raise CollectionError(
                            f"unsafe output entry (expected a regular file or directory): {path}"
                        )
    if actual != set(expected):
        raise CollectionError(
            f"output boundary differs: missing={sorted(set(expected) - actual)}, "
            f"unexpected={sorted(actual - set(expected))}"
        )


def _validate_provenance(
    relative: str, item: InventoryRecord, selection: Entry
) -> None:
    """Check manifest identity and inventory metadata for one document."""
    if (
        item["repository"] != selection.repository
        or item["source"] != selection.source.as_posix()
    ):
        raise CollectionError(f"inventory provenance differs from manifest: {relative}")
    if not isinstance(item["commit"], str) or not SHA_RE.fullmatch(item["commit"]):
        raise CollectionError(f"invalid inventory commit: {relative}")
    if (
        not isinstance(item["status"], str)
        or item["status"] not in DOCUMENTATION_STATUSES
    ):
        raise CollectionError(f"invalid inventory status: {relative}")
    if not isinstance(item["license"], str) or not SPDX_RE.fullmatch(item["license"]):
        raise CollectionError(f"invalid inventory license: {relative}")
    if not isinstance(item["attribution"], str) or UNSAFE_ATTRIBUTION_RE.search(
        item["attribution"]
    ):
        raise CollectionError(f"invalid inventory attribution: {relative}")
    if selection.source_name == "dasc" and not item["attribution"].strip():
        raise CollectionError(f"missing inventory attribution: {relative}")


def _read_checked_document(path: Path, relative: str, item: InventoryRecord) -> bytes:
    """Read through the regular-file guard and verify the content checksum."""
    data = read_regular_file(path, "generated document")
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise CollectionError(f"checksum mismatch: {relative}")
    return data


def _validate_markdown_provenance(
    text: str, relative: str, item: InventoryRecord
) -> None:
    """Reject forbidden content or a missing/mismatched generated banner."""
    encoded_source = quote(item["source"], safe="/")
    source_url = f"{item['repository']}/blob/{item['commit']}/{encoded_source}"
    banner = (
        f"<!-- Generated; source={source_url}; status={item['status']}; "
        f"license={item['license']}; attribution={item['attribution']}; "
        "do not edit. -->\n"
    )
    if FORBIDDEN.search(text) or not text.startswith(banner):
        raise CollectionError(f"unsafe/missing provenance: {relative}")


def _validate_links(text: str, path: Path, docs: Path, relative: str) -> None:
    """Validate rendered Markdown links and image destinations."""
    matches = _markdown_link_matches(
        text,
        PurePosixPath(relative),
    )
    for match in matches:
        raw = unescape(match.destination)
        parsed = _split_link(raw, PurePosixPath(relative))
        if parsed.scheme in {"http", "https", "mailto"} or raw.startswith("#"):
            if match.label.startswith("!"):
                raise CollectionError(f"image is not approved: {relative}: {raw}")
            continue
        if parsed.scheme or parsed.netloc or raw.startswith("/"):
            raise CollectionError(f"unsafe link: {relative}: {raw}")
        if not parsed.path:
            if match.label.startswith("!"):
                raise CollectionError(f"image is not approved: {relative}: {raw}")
            continue
        decoded_path = _decode_link_path(parsed.path, PurePosixPath(relative))
        target = path.parent.joinpath(*decoded_path.parts).resolve()
        if not target.is_relative_to(docs) or not target.is_file():
            raise CollectionError(f"broken link: {relative}: {raw}")


def validate(manifest: Path, docs: Path) -> None:
    selected = {
        entry.destination.as_posix(): entry for entry in load_manifest(manifest)
    }
    docs = docs.resolve()
    expected = _load_inventory(docs, selected)
    _validate_tree(docs, expected)
    # Finish each document before checking the next to preserve error precedence.
    for relative, item in expected.items():
        selection = selected[relative]
        _validate_provenance(relative, item, selection)
        path = docs / relative
        data = _read_checked_document(path, relative, item)
        if path.suffix.lower() == ".md":
            text = data.decode("utf-8")
            _validate_markdown_provenance(text, relative, item)
            _validate_links(text, path, docs, relative)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.manifest, args.docs)
    except (CollectionError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
