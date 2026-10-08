#!/usr/bin/env python3
"""Validate generated structure/provenance; source approval remains a collector check."""

from __future__ import annotations
import argparse
import hashlib
import os
import stat
import sys
from html import unescape
from pathlib import Path, PurePosixPath
from publication_errors import CollectionError
from publication_policy import (
    DOCUMENTATION_STATUSES,
    EXPECTED,
    FORBIDDEN,
    SHA_RE,
    SPDX_RE,
    UNSAFE_ATTRIBUTION_RE,
)
from publication_models import InventoryRecord, SelectedEntry, provenance_banner
from source_manifest import load_manifest
from safe_files import check_inventory_path as _check_inventory_path, read_regular_file
from structured_input import read_json
from markdown_policy import _decode_link_path, _markdown_link_matches, _split_link


def read_inventory(docs: Path) -> dict[str, InventoryRecord]:
    path = docs / "generated-inventory.json"
    _check_inventory_path(path, required=True)
    data = read_json(read_regular_file(path, "inventory"), "inventory")
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "files"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["files"], list)
    ):
        raise CollectionError("invalid inventory schema")
    required = set(InventoryRecord.__dataclass_fields__)
    records = {}
    for index, item in enumerate(data["files"]):
        if not isinstance(item, dict) or set(item) != required:
            raise CollectionError(f"invalid inventory item at index {index}")
        for key in required:
            if not isinstance(item[key], str):
                raise CollectionError(f"invalid inventory {key} at index {index}")
        record = InventoryRecord(**item)
        if record.destination in records:
            raise CollectionError("duplicate inventory destination")
        records[record.destination] = record
    return records


def reconcile_selection(records, selected) -> None:
    if set(records) != set(selected):
        raise CollectionError(
            f"inventory differs from manifest: missing={sorted(set(selected) - set(records))}, "
            f"unexpected={sorted(set(records) - set(selected))}"
        )


def generated_files(docs: Path) -> set[str]:
    actual = set()
    for namespace in EXPECTED:
        root = docs / namespace
        if root.is_symlink() or not root.is_dir():
            raise CollectionError(f"missing/unsafe namespace: {namespace}")
        pending = [root]
        while pending:
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
    return actual


def validate_provenance(item: InventoryRecord, selection: SelectedEntry) -> None:
    relative = item.destination
    if item.repository != selection.repository or item.source != selection.source.as_posix():
        raise CollectionError(f"inventory provenance differs from manifest: {relative}")
    if not SHA_RE.fullmatch(item.commit):
        raise CollectionError(f"invalid inventory commit: {relative}")
    if item.status not in DOCUMENTATION_STATUSES:
        raise CollectionError(f"invalid inventory status: {relative}")
    if not SPDX_RE.fullmatch(item.license):
        raise CollectionError(f"invalid inventory license: {relative}")
    if UNSAFE_ATTRIBUTION_RE.search(item.attribution):
        raise CollectionError(f"invalid inventory attribution: {relative}")
    if selection.source_name == "dasc" and not item.attribution.strip():
        raise CollectionError(f"missing inventory attribution: {relative}")


def validate_generated_links(text: str, relative: str, path: Path, docs: Path) -> None:
    for match in _markdown_link_matches(text, PurePosixPath(relative)):
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
        decoded = _decode_link_path(parsed.path, PurePosixPath(relative))
        target = path.parent.joinpath(*decoded.parts).resolve()
        if not target.is_relative_to(docs) or not target.is_file():
            raise CollectionError(f"broken link: {relative}: {raw}")


def validate_document(item: InventoryRecord, docs: Path) -> None:
    path = docs / item.destination
    data = read_regular_file(path, "generated document")
    if hashlib.sha256(data).hexdigest() != item.sha256:
        raise CollectionError(f"checksum mismatch: {item.destination}")
    if path.suffix.lower() == ".md":
        text = data.decode("utf-8")
        if FORBIDDEN.search(text) or not text.startswith(provenance_banner(item.mapping())):
            raise CollectionError(f"unsafe/missing provenance: {item.destination}")
        validate_generated_links(text, item.destination, path, docs)


def validate(manifest: Path, docs: Path) -> None:
    selected = {entry.destination.as_posix(): entry for entry in load_manifest(manifest)}
    docs = docs.resolve()
    records = read_inventory(docs)
    reconcile_selection(records, selected)
    actual = generated_files(docs)
    if actual != set(records):
        raise CollectionError(
            f"output boundary differs: missing={sorted(set(records) - actual)}, unexpected={sorted(actual - set(records))}"
        )
    for relative, record in records.items():
        validate_provenance(record, selected[relative])
        validate_document(record, docs)


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
