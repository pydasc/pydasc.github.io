#!/usr/bin/env python3
"""Assemble approved documentation from exact local source checkouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import SplitResult, quote, unquote_to_bytes, urlsplit

import yaml

EXPECTED = {
    "pydasc": "https://github.com/pydasc/pydasc",
    "dasc": "https://github.com/pydasc/dasc",
}
# Repository transfers preserve history, but the source repositories currently
# publish contracts bearing their former URLs. Accept only these exact aliases;
# the website manifest and fetch workflows still require the canonical org URLs.
LEGACY_CONTRACT_REPOSITORIES = {
    "pydasc": "https://github.com/chongshikpark/pydasc",
    "dasc": "https://github.com/chongshikpark/dasc",
}
ALLOWED = {".md", ".png", ".jpg", ".jpeg", ".webp"}
MEDIA = {".md": "text/markdown", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_FILE_BYTES = 5 * 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SPDX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
DOCUMENTATION_STATUSES = {
    "Draft", "Reviewed", "Reference", "Validated", "Unvalidated",
    "Superseded", "Released",
}
LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
REFERENCE_LINK_RE = re.compile(r"^\s{0,3}\[(?!\^)[^\]]+\]:", re.MULTILINE)
MARKDOWN_AUTOLINK_RE = re.compile(
    r"<(?:https?://[^<>\s]+|[^<>\s@]+@[^<>\s@]+)>"
)
HTML_TAG_START_RE = re.compile(r"<\s*/?\s*[A-Za-z][A-Za-z0-9-]*")
ACTIVE_HTML_TAGS = {
    "a", "audio", "base", "button", "canvas", "embed", "form", "iframe",
    "img", "input", "link", "meta", "object", "option", "script", "select",
    "source", "style", "svg", "textarea", "track", "video",
}
UNSAFE_HTML_ATTRIBUTES = {
    "action", "archive", "background", "cite", "classid", "codebase", "data",
    "formaction", "href", "longdesc", "manifest", "ping", "poster", "profile",
    "src", "srcset", "style", "usemap", "xlink:href",
}
UNSAFE_ATTRIBUTION_RE = re.compile(r"[\x00-\x1f<>\[\]]")
FORBIDDEN = re.compile(r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+|AKIA[0-9A-Z]{16}|/(?:Users|home)/[^\s)`]+|https?://(?:localhost|127\.0\.0\.1|[^/\s]+\.internal)(?:[/\s)]|$))")


class CollectionError(ValueError):
    pass


class UnapprovedPublicationError(CollectionError):
    """A structurally valid source contract is not approved for publication."""


class MarkdownHTMLGuard(HTMLParser):
    """Reject executable or resource-loading raw HTML in imported Markdown."""

    def __init__(self, source: PurePosixPath) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source

    def _reject(self) -> None:
        raise CollectionError(f"active raw HTML is not allowed: {self.source}")

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        raw = self.get_starttag_text() or ""
        if MARKDOWN_AUTOLINK_RE.fullmatch(raw):
            return
        if tag.casefold() in ACTIVE_HTML_TAGS:
            self._reject()
        for name, _ in attrs:
            folded = name.casefold()
            if folded.startswith("on") or folded in UNSAFE_HTML_ATTRIBUTES:
                self._reject()

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_pi(self, data: str) -> None:
        del data
        self._reject()


def _validate_markdown_html(text: str, source: PurePosixPath) -> None:
    try:
        position = 0
        while match := HTML_TAG_START_RE.search(text, position):
            if match.end() < len(text) and text[match.end()] not in " \t\r\n/>":
                position = match.end()
                continue
            quote = ""
            cursor = match.end()
            while cursor < len(text):
                character = text[cursor]
                if quote:
                    if character == quote:
                        quote = ""
                elif character in "\"'":
                    quote = character
                elif character == ">":
                    MarkdownHTMLGuard(source).feed(text[match.start():cursor + 1])
                    position = cursor + 1
                    break
                elif character == "<":
                    position = cursor
                    break
                cursor += 1
            else:
                break
    except CollectionError:
        raise
    except Exception as exc:
        raise CollectionError(f"invalid raw HTML in {source}") from exc


@dataclass(frozen=True)
class Entry:
    source_name: str
    repository: str
    checkout_commit: str
    content_commit: str
    source: PurePosixPath
    destination: PurePosixPath
    status: str
    license_id: str
    attribution: str


def _mapping(value: object, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise CollectionError(f"{context} keys invalid (missing={sorted(keys-actual)}, unknown={sorted(actual-keys)})")
    return value


def _path(value: object, context: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value:
        raise CollectionError(f"{context} must be a non-empty POSIX path")
    result = PurePosixPath(value)
    if result.is_absolute() or any(part in {"", ".", ".."} for part in result.parts) or any(c in value for c in "*?["):
        raise CollectionError(f"unsafe {context}: {value!r}")
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CollectionError(f"cannot read website manifest: {exc}") from exc


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    try:
        result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=not binary)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise CollectionError(f"git inspection failed in {repo.name}") from exc
    return result.stdout


def _decode_link_path(raw: str, source: PurePosixPath) -> PurePosixPath:
    """Strictly decode and validate an imported relative URL path."""
    if re.search(r"%(?![0-9A-Fa-f]{2})", raw):
        raise CollectionError(f"invalid percent escape in link path: {raw!r}")
    try:
        decoded = unquote_to_bytes(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollectionError(f"link path is not valid UTF-8: {raw!r}") from exc
    if "\\" in decoded or any(ord(character) < 0x20 or ord(character) == 0x7f for character in decoded):
        raise CollectionError(f"unsafe link path {raw!r} in {source}")
    return PurePosixPath(decoded)


def _split_link(raw: str, source: PurePosixPath) -> SplitResult:
    """Parse an imported URL without exposing parser exceptions."""
    try:
        return urlsplit(raw)
    except ValueError as exc:
        raise CollectionError(f"invalid link URL {raw!r} in {source}") from exc


def _git_object_kind(
    repo: Path, commit: str, path: PurePosixPath
) -> str | None:
    """Return the safe Git object type for an exact path at an exact commit."""
    raw = _git(
        repo,
        "ls-tree",
        "-z",
        "--full-tree",
        commit,
        "--",
        path.as_posix(),
        binary=True,
    )
    assert isinstance(raw, bytes)
    expected = path.as_posix().encode("utf-8")
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, encoded_path = record.partition(b"\t")
        fields = metadata.split()
        if separator and encoded_path == expected and len(fields) == 3:
            mode, object_type, _ = fields
            if mode == b"120000" or object_type not in {b"blob", b"tree"}:
                return None
            return object_type.decode("ascii")
    return None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _source_contract(
    path: Path,
    name: str,
    repository: str,
    checkout: str,
    raw_contract: bytes | None = None,
) -> tuple[str, dict[str, dict[str, Any]]]:
    try:
        raw = json.loads(
            raw_contract if raw_contract is not None else path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"cannot read {name} publication manifest: {exc}") from exc
    root_keys = {"schema_version", "project", "repository", "source_commit", "files"}
    if name == "dasc":
        root_keys.add("publication_decision")
    root = _mapping(raw, root_keys, f"{name} publication manifest")
    accepted_repository = root["repository"] in {
        repository,
        LEGACY_CONTRACT_REPOSITORIES[name],
    }
    if root["schema_version"] != 1 or root["project"] != name or not accepted_repository:
        raise CollectionError(f"invalid {name} publication identity/schema")
    content = root["source_commit"]
    if not isinstance(content, str) or not SHA_RE.fullmatch(content):
        raise CollectionError(f"invalid {name} source_commit")
    if name == "dasc":
        decision = _mapping(root["publication_decision"], {"state", "reason", "evidence"}, "dasc decision")
        if decision["state"] != "approved":
            raise UnapprovedPublicationError("DASC publication decision is not approved")
        if any(
            not isinstance(decision[field], str) or not decision[field].strip()
            for field in ("reason", "evidence")
        ):
            raise CollectionError("invalid DASC publication decision evidence")
    if _git(path.parents[1], "rev-parse", "HEAD").strip() != checkout:
        raise CollectionError(f"{name} checkout commit mismatch")
    approved: dict[str, dict[str, Any]] = {}
    approved_sources: set[str] = set()
    approved_destinations: set[str] = set()
    if not isinstance(root["files"], list):
        raise CollectionError(f"{name} files must be a list")
    for index, item in enumerate(root["files"]):
        item = _mapping(item, {"source", "destination", "media_type", "documentation_status", "redistribution"}, f"{name}.files[{index}]")
        source = _path(item["source"], "source")
        destination = _path(item["destination"], "destination")
        if destination.parts[0] != name or source.suffix.lower() not in ALLOWED or item["media_type"] != MEDIA[source.suffix.lower()]:
            raise CollectionError(f"invalid approved file: {source}")
        folded_source = source.as_posix().casefold()
        folded_destination = destination.as_posix().casefold()
        if folded_source in approved_sources:
            raise CollectionError(f"duplicate approved source: {source}")
        if folded_destination in approved_destinations:
            raise CollectionError(f"duplicate approved destination: {destination}")
        approved_sources.add(folded_source)
        approved_destinations.add(folded_destination)
        status = _mapping(item["documentation_status"], {"label", "evidence"}, "status")
        if status["label"] not in DOCUMENTATION_STATUSES or not isinstance(status["evidence"], str) or not status["evidence"].strip():
            raise CollectionError(f"invalid status for {source}")
        rights_keys = {"spdx_license", "license_file"} | ({"attribution"} if name == "dasc" else set())
        rights = _mapping(item["redistribution"], rights_keys, "redistribution")
        if not isinstance(rights["spdx_license"], str) or not SPDX_RE.fullmatch(rights["spdx_license"]):
            raise CollectionError(f"invalid SPDX license for {source}")
        if name == "dasc" and (
            not isinstance(rights["attribution"], str)
            or not rights["attribution"].strip()
            or UNSAFE_ATTRIBUTION_RE.search(rights["attribution"])
        ):
            raise CollectionError(f"invalid attribution for {source}")
        license_path = _path(rights["license_file"], "license_file")
        license_bytes = _git(path.parents[1], "show", f"{content}:{license_path.as_posix()}", binary=True)
        if not license_bytes:
            raise CollectionError(f"missing license at approved commit for {source}")
        approved[source.as_posix()] = {**item, "_destination": destination, "_status": status["label"], "_license": rights["spdx_license"], "_attribution": rights.get("attribution", "")}
    return content, approved


def load_manifest(path: Path, checkouts: dict[str, Path] | None = None) -> list[Entry]:
    root = _mapping(_read_yaml(path), {"schema_version", "sources"}, "website manifest")
    if root["schema_version"] != 2 or not isinstance(root["sources"], dict) or set(root["sources"]) != set(EXPECTED):
        raise CollectionError("website manifest must be schema 2 with exactly pydasc and dasc")
    entries: list[Entry] = []
    destinations: set[str] = set()
    for name, repository in EXPECTED.items():
        source = _mapping(root["sources"][name], {"repository", "checkout_commit", "publication_manifest", "files"}, f"source {name}")
        checkout_commit = source["checkout_commit"]
        if source["repository"] != repository or not isinstance(checkout_commit, str) or not SHA_RE.fullmatch(checkout_commit):
            raise CollectionError(f"invalid lock identity/commit for {name}")
        manifest_rel = _path(source["publication_manifest"], "publication_manifest")
        if not isinstance(source["files"], list) or not source["files"]:
            raise CollectionError(f"{name} lock files must be non-empty")
        approved: dict[str, dict[str, Any]] = {}
        content_commit = "0" * 40
        if checkouts is not None:
            checkout = checkouts[name].resolve()
            contract = checkout.joinpath(*manifest_rel.parts)
            if contract.is_symlink() or not _inside(contract.resolve(), checkout):
                raise CollectionError(f"unsafe {name} publication manifest")
            if _git(checkout, "rev-parse", "HEAD").strip() != checkout_commit:
                raise CollectionError(f"{name} checkout commit mismatch")
            committed_contract = _git(
                checkout,
                "show",
                f"{checkout_commit}:{manifest_rel.as_posix()}",
                binary=True,
            )
            try:
                working_contract = contract.read_bytes()
            except OSError as exc:
                raise CollectionError(f"cannot read {name} publication manifest") from exc
            if working_contract != committed_contract:
                raise CollectionError(
                    f"{name} publication manifest differs from locked commit"
                )
            content_commit, approved = _source_contract(
                contract,
                name,
                repository,
                checkout_commit,
                committed_contract,
            )
        for index, selected in enumerate(source["files"]):
            selected = _mapping(selected, {"source", "destination"}, f"{name}.files[{index}]")
            src = _path(selected["source"], "source")
            dest = _path(selected["destination"], "destination")
            if dest.parts[0] != name or src.suffix.lower() not in ALLOWED or src.suffix.lower() != dest.suffix.lower():
                raise CollectionError(f"invalid selected file {src} -> {dest}")
            folded = dest.as_posix().casefold()
            if folded in destinations:
                raise CollectionError(f"duplicate destination: {dest}")
            destinations.add(folded)
            if checkouts is not None:
                offer = approved.get(src.as_posix())
                if offer is None or offer["_destination"] != dest:
                    raise CollectionError(f"missing source approval: {src} -> {dest}")
                entries.append(Entry(name, repository, checkout_commit, content_commit, src, dest, offer["_status"], offer["_license"], offer["_attribution"]))
            else:
                entries.append(Entry(name, repository, checkout_commit, content_commit, src, dest, "", "", ""))
    return entries


def _rewrite(text: str, entry: Entry, selected: dict[tuple[str, str], Entry], checkout: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        label, raw = match.groups()
        parsed = _split_link(raw, entry.source)
        if parsed.scheme in {"http", "https", "mailto"} or raw.startswith("#"):
            return match.group(0)
        if parsed.scheme or parsed.netloc or raw.startswith("/"):
            raise CollectionError(f"unsafe link {raw!r} in {entry.source}")
        if not parsed.path:
            return match.group(0)
        relative_path = _decode_link_path(parsed.path, entry.source)
        parts: list[str] = []
        for part in entry.source.parent.joinpath(relative_path).parts:
            if part == "..":
                if not parts:
                    raise CollectionError(f"link escapes repository: {raw}")
                parts.pop()
            elif part not in {"", "."}:
                parts.append(part)
        normalized = PurePosixPath(*parts)
        approved = selected.get((entry.source_name, normalized.as_posix()))
        if approved:
            relocated = os.path.relpath(
                approved.destination.as_posix(),
                entry.destination.parent.as_posix(),
            ).replace(os.sep, "/")
            target = quote(relocated, safe="/")
        else:
            kind = _git_object_kind(checkout, entry.content_commit, normalized)
            if kind is None:
                raise CollectionError(f"broken or unsafe relative link: {raw}")
            if label.startswith("!"):
                raise CollectionError(f"image is not approved: {raw}")
            encoded_path = quote(normalized.as_posix(), safe="/")
            target = f"{entry.repository}/{kind}/{entry.content_commit}/{encoded_path}"
        suffix = (f"?{parsed.query}" if parsed.query else "") + (f"#{parsed.fragment}" if parsed.fragment else "")
        return f"{label}({target}{suffix})"
    return LINK_RE.sub(replace, text)


def _tree_state(repo: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    files = []
    for raw in _git(repo, "ls-files", "-co", "--exclude-standard").splitlines():
        path = repo / raw
        if path.is_file() and not path.is_symlink():
            files.append((raw, hashlib.sha256(path.read_bytes()).hexdigest()))
    return status, tuple(files)


def assemble(manifest: Path, output: Path, pydasc: Path, dasc: Path) -> list[dict[str, Any]]:
    checkouts = {"pydasc": pydasc.resolve(), "dasc": dasc.resolve()}
    before = {name: _tree_state(repo) for name, repo in checkouts.items()}
    entries = load_manifest(manifest, checkouts)
    selected = {(entry.source_name, entry.source.as_posix()): entry for entry in entries}
    inventory: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dasc-assembly-") as temporary:
        stage = Path(temporary) / "docs"
        for entry in entries:
            root = checkouts[entry.source_name]
            source = root.joinpath(*entry.source.parts)
            if source.is_symlink() or not _inside(source.resolve(strict=False), root) or not source.is_file():
                raise CollectionError(f"unsafe or missing source: {entry.source}")
            if source.stat().st_size > MAX_FILE_BYTES:
                raise CollectionError(f"oversized source: {entry.source}")
            committed = _git(root, "show", f"{entry.content_commit}:{entry.source.as_posix()}", binary=True)
            if source.read_bytes() != committed:
                raise CollectionError(f"source differs from approved commit: {entry.source}")
            destination = stage.joinpath(*entry.destination.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if entry.source.suffix.lower() == ".md":
                try:
                    body = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                except UnicodeDecodeError as exc:
                    raise CollectionError(f"non-UTF-8 Markdown: {entry.source}") from exc
                if FORBIDDEN.search(body):
                    raise CollectionError(f"credential-like or local content: {entry.source}")
                _validate_markdown_html(body, entry.source)
                if REFERENCE_LINK_RE.search(body):
                    raise CollectionError(f"reference-style links are not allowed: {entry.source}")
                body = _rewrite(body, entry, selected, root)
                encoded_source = quote(entry.source.as_posix(), safe="/")
                source_url = (
                    f"{entry.repository}/blob/{entry.content_commit}/{encoded_source}"
                )
                project = "PyDASC" if entry.source_name == "pydasc" else "DASC"
                banner = f"<!-- Generated; source={source_url}; status={entry.status}; license={entry.license_id}; attribution={entry.attribution}; do not edit. -->\n\n"
                attribution = (
                    f"    **Attribution:** {entry.attribution}  \n"
                    if entry.attribution
                    else ""
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
            inventory.append({"destination": entry.destination.as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "repository": entry.repository, "source": entry.source.as_posix(), "commit": entry.content_commit, "status": entry.status, "license": entry.license_id, "attribution": entry.attribution})
        output = output.resolve()
        for name in EXPECTED:
            target = output / name
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise CollectionError(f"unsafe generated namespace: {target}")
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(stage / name, target)
        inventory.sort(key=lambda item: item["destination"])
        (output / "generated-inventory.json").write_text(json.dumps({"schema_version": 1, "files": inventory}, indent=2, sort_keys=True) + "\n")
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
    except CollectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
