#!/usr/bin/env python3
"""Validate assembled docs and checksummed inventory."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from collect_docs import CollectionError, EXPECTED, FORBIDDEN, LINK_RE, load_manifest

def validate(manifest: Path, docs: Path) -> None:
    selected = {entry.destination.as_posix(): entry for entry in load_manifest(manifest)}
    docs = docs.resolve()
    try: inventory = json.loads((docs / "generated-inventory.json").read_text())
    except (OSError, json.JSONDecodeError) as exc: raise CollectionError(f"invalid inventory: {exc}") from exc
    if set(inventory) != {"schema_version", "files"} or inventory["schema_version"] != 1 or not isinstance(inventory["files"], list): raise CollectionError("invalid inventory schema")
    expected = {item["destination"]: item for item in inventory["files"]}
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
        if set(item) != {"destination", "sha256", "repository", "source", "commit", "status", "license"}: raise CollectionError(f"invalid inventory item: {relative}")
        selection = selected[relative]
        if item["repository"] != selection.repository or item["source"] != selection.source.as_posix():
            raise CollectionError(f"inventory provenance differs from manifest: {relative}")
        path = docs / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]: raise CollectionError(f"checksum mismatch: {relative}")
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            if FORBIDDEN.search(text) or not text.startswith("<!-- Generated; source="): raise CollectionError(f"unsafe/missing provenance: {relative}")
            for match in LINK_RE.finditer(text):
                raw = match.group(2); parsed = urlsplit(raw)
                if parsed.scheme in {"http", "https", "mailto"} or raw.startswith("#"): continue
                if parsed.scheme or parsed.netloc or raw.startswith("/"): raise CollectionError(f"unsafe link: {relative}: {raw}")
                target = (path.parent / unquote(parsed.path)).resolve()
                if not target.is_relative_to(docs) or not target.is_file(): raise CollectionError(f"broken link: {relative}: {raw}")

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--manifest",type=Path,required=True); parser.add_argument("--docs",type=Path,required=True); args=parser.parse_args()
    try: validate(args.manifest,args.docs)
    except (CollectionError,OSError,UnicodeError) as exc: print(f"error: {exc}",file=sys.stderr); return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
