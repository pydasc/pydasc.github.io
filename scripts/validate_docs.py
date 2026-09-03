#!/usr/bin/env python3
"""Validate assembled docs and checksummed inventory."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from collect_docs import (
    DOCUMENTATION_STATUSES,
    EXPECTED,
    FORBIDDEN,
    SHA_RE,
    SPDX_RE,
    UNSAFE_ATTRIBUTION_RE,
    CollectionError,
    _decode_link_path,
    _markdown_link_matches,
    _split_link,
    load_manifest,
)

def validate(manifest: Path, docs: Path) -> None:
    selected = {entry.destination.as_posix(): entry for entry in load_manifest(manifest)}
    docs = docs.resolve()
    try: inventory = json.loads((docs / "generated-inventory.json").read_text())
    except (OSError, json.JSONDecodeError) as exc: raise CollectionError(f"invalid inventory: {exc}") from exc
    if not isinstance(inventory, dict) or set(inventory) != {"schema_version", "files"} or inventory["schema_version"] != 1 or not isinstance(inventory["files"], list): raise CollectionError("invalid inventory schema")
    required_item_keys = {"destination", "sha256", "repository", "source", "commit", "status", "license", "attribution"}
    expected = {}
    for index, item in enumerate(inventory["files"]):
        if not isinstance(item, dict) or set(item) != required_item_keys:
            raise CollectionError(f"invalid inventory item at index {index}")
        destination = item["destination"]
        if not isinstance(destination, str):
            raise CollectionError(f"invalid inventory destination at index {index}")
        expected[destination] = item
    if len(expected) != len(inventory["files"]): raise CollectionError("duplicate inventory destination")
    if set(expected) != set(selected):
        raise CollectionError(
            f"inventory differs from manifest: missing={sorted(set(selected)-set(expected))}, "
            f"unexpected={sorted(set(expected)-set(selected))}"
        )
    actual: set[str] = set()
    for namespace in EXPECTED:
        root = docs / namespace
        if root.is_symlink() or not root.is_dir(): raise CollectionError(f"missing/unsafe namespace: {namespace}")
        for path in root.rglob("*"):
            if path.is_symlink(): raise CollectionError(f"output symlink: {path}")
            if path.is_file(): actual.add(path.relative_to(docs).as_posix())
    if actual != set(expected): raise CollectionError(f"output boundary differs: missing={sorted(set(expected)-actual)}, unexpected={sorted(actual-set(expected))}")
    for relative, item in expected.items():
        selection = selected[relative]
        if item["repository"] != selection.repository or item["source"] != selection.source.as_posix():
            raise CollectionError(f"inventory provenance differs from manifest: {relative}")
        if not isinstance(item["commit"], str) or not SHA_RE.fullmatch(item["commit"]):
            raise CollectionError(f"invalid inventory commit: {relative}")
        if not isinstance(item["status"], str) or item["status"] not in DOCUMENTATION_STATUSES:
            raise CollectionError(f"invalid inventory status: {relative}")
        if not isinstance(item["license"], str) or not SPDX_RE.fullmatch(item["license"]):
            raise CollectionError(f"invalid inventory license: {relative}")
        if not isinstance(item["attribution"], str) or UNSAFE_ATTRIBUTION_RE.search(item["attribution"]):
            raise CollectionError(f"invalid inventory attribution: {relative}")
        if selection.source_name == "dasc" and not item["attribution"].strip():
            raise CollectionError(f"missing inventory attribution: {relative}")
        path = docs / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]: raise CollectionError(f"checksum mismatch: {relative}")
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            encoded_source = quote(item["source"], safe="/")
            source_url = (
                f"{item['repository']}/blob/{item['commit']}/{encoded_source}"
            )
            banner = f"<!-- Generated; source={source_url}; status={item['status']}; license={item['license']}; attribution={item['attribution']}; do not edit. -->\n"
            if FORBIDDEN.search(text) or not text.startswith(banner): raise CollectionError(f"unsafe/missing provenance: {relative}")
            for match in _markdown_link_matches(text, PurePosixPath(relative)):
                raw = match.group(2); parsed = _split_link(raw, PurePosixPath(relative))
                if parsed.scheme in {"http", "https", "mailto"} or raw.startswith("#"): continue
                if parsed.scheme or parsed.netloc or raw.startswith("/"): raise CollectionError(f"unsafe link: {relative}: {raw}")
                if not parsed.path: continue
                decoded_path = _decode_link_path(parsed.path, PurePosixPath(relative))
                target = path.parent.joinpath(*decoded_path.parts).resolve()
                if not target.is_relative_to(docs) or not target.is_file(): raise CollectionError(f"broken link: {relative}: {raw}")

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--manifest",type=Path,required=True); parser.add_argument("--docs",type=Path,required=True); args=parser.parse_args()
    try: validate(args.manifest,args.docs)
    except (CollectionError,OSError,UnicodeError) as exc: print(f"error: {exc}",file=sys.stderr); return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
