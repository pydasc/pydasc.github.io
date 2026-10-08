"""Conservative Markdown source analysis, rendered probing and approved rewriting."""

from __future__ import annotations
import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from urllib.parse import SplitResult, quote, unquote_to_bytes, urlsplit
import markdown
from html_policy import unique_attributes
from publication_errors import CollectionError
from publication_models import ApprovedEntry as Entry
from git_inspection import object_kind as _git_object_kind
from publication_policy import (
    MARKDOWN_AUTOLINK_RE,
    BLOCKQUOTE_PREFIX_RE,
    LIST_PREFIX_RE,
    HTML_TAG_START_RE,
    ACTIVE_HTML_TAGS,
    UNSAFE_HTML_ATTRIBUTES,
    MARKDOWN_POLICY_EXTENSIONS,
    RENDER_ALLOWED_ATTRIBUTES,
    RENDER_FORBIDDEN_TAGS,
)


class MarkdownHTMLGuard(HTMLParser):
    """Reject executable or resource-loading raw HTML in imported Markdown."""

    def __init__(self, source: PurePosixPath) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source

    def _reject(self) -> None:
        raise CollectionError(f"active raw HTML is not allowed: {self.source}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        if MARKDOWN_AUTOLINK_RE.fullmatch(raw):
            return
        if tag.casefold() in ACTIVE_HTML_TAGS:
            self._reject()
        for name, _ in attrs:
            folded = name.casefold()
            if folded.startswith("on") or folded in UNSAFE_HTML_ATTRIBUTES:
                self._reject()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_pi(self, data: str) -> None:
        del data
        self._reject()


class RenderedReferenceParser(HTMLParser):
    """Collect links and images emitted by the configured Markdown parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        try:
            values = unique_attributes(attrs)
        except ValueError as exc:
            raise CollectionError(str(exc)) from exc
        if tag == "a" and values.get("href") is not None:
            self.references.append(("link", values["href"] or ""))
        elif tag == "img" and values.get("src") is not None:
            self.references.append(("image", values["src"] or ""))


class RenderedHTMLGuard(HTMLParser):
    """Reject active elements or unsafe attributes in the rendered HTML."""

    def __init__(self, source: PurePosixPath) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source

    def _reject(self, reason: str) -> None:
        raise CollectionError(f"{reason}: {self.source}")

    def _check(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        try:
            values = unique_attributes(attrs)
        except ValueError as exc:
            raise CollectionError(f"{exc}: {self.source}") from exc
        folded_tag = tag.casefold()
        if folded_tag in RENDER_FORBIDDEN_TAGS:
            self._reject("active rendered HTML is not allowed")
        allowed = RENDER_ALLOWED_ATTRIBUTES.get(folded_tag, frozenset())
        for name, _ in attrs:
            folded = name.casefold()
            if folded in allowed:
                continue
            if folded.startswith("on") or folded in UNSAFE_HTML_ATTRIBUTES:
                self._reject("unsafe rendered attribute is not allowed")
        for name in allowed:
            if values.get(name) is not None:
                _validate_rendered_url(values[name] or "", self.source, folded_tag == "img")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._check(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._check(tag, attrs)


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
                    MarkdownHTMLGuard(source).feed(text[match.start() : cursor + 1])
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
class MarkdownLink:
    label: str
    destination: str
    destination_start: int
    destination_end: int


def _decode_link_path(raw: str, source: PurePosixPath) -> PurePosixPath:
    """Strictly decode and validate an imported relative URL path."""
    if re.search(r"%(?![0-9A-Fa-f]{2})", raw):
        raise CollectionError(f"invalid percent escape in link path: {raw!r}")
    try:
        decoded = unquote_to_bytes(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollectionError(f"link path is not valid UTF-8: {raw!r}") from exc
    if "\\" in decoded or any(
        ord(character) < 0x20 or ord(character) == 0x7F for character in decoded
    ):
        raise CollectionError(f"unsafe link path {raw!r} in {source}")
    return PurePosixPath(decoded)


def _split_link(raw: str, source: PurePosixPath) -> SplitResult:
    """Parse an imported URL without exposing parser exceptions."""
    try:
        return urlsplit(raw)
    except ValueError as exc:
        raise CollectionError(f"invalid link URL {raw!r} in {source}") from exc


def _validate_rendered_url(raw: str, source: PurePosixPath, image: bool) -> None:
    """Check actual DOM destinations even when source matching finds no link."""
    if "\\" in raw or any(ord(c) < 0x20 or ord(c) == 0x7F for c in raw):
        raise CollectionError(f"unsafe rendered URL in {source}: {raw!r}")
    parsed = _split_link(raw, source)
    if parsed.scheme not in {"", "http", "https", "mailto"} or (
        not parsed.scheme and (parsed.netloc or raw.startswith("/"))
    ):
        raise CollectionError(f"unsafe link {raw!r} in {source}")
    if image and (parsed.scheme or not parsed.path):
        raise CollectionError(f"image is not approved: {raw}")


def _markdown_visible_text(text: str) -> str:
    """Mask Markdown code and escapes while retaining source offsets."""
    masked = list(text)
    fenced = False
    fence_character = ""
    fence_length = 0
    fence_quote_depth = 0
    fence_list_indent = 0
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line
        quote_depth = 0
        while quote := BLOCKQUOTE_PREFIX_RE.match(content):
            content = content[quote.end() :]
            quote_depth += 1
        marker_content = content
        list_indent = 0
        if fenced and fence_list_indent:
            indentation = re.match(r"^[ ]+", marker_content)
            if indentation and len(indentation.group(0)) >= fence_list_indent:
                marker_content = marker_content[fence_list_indent:]
        elif not fenced and (list_prefix := LIST_PREFIX_RE.match(marker_content)):
            list_indent = list_prefix.end()
            marker_content = marker_content[list_indent:]
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", marker_content)
        if fenced:
            masked[offset : offset + len(line)] = " " * len(line)
            if (
                marker
                and quote_depth == fence_quote_depth
                and marker.group(1)[0] == fence_character
                and len(marker.group(1)) >= fence_length
                and not marker_content[marker.end() :].strip()
            ):
                fenced = False
        elif marker:
            fenced = True
            fence_character = marker.group(1)[0]
            fence_length = len(marker.group(1))
            fence_quote_depth = quote_depth
            fence_list_indent = list_indent
            masked[offset : offset + len(line)] = " " * len(line)
        elif content.startswith(("    ", "\t")):
            masked[offset : offset + len(line)] = " " * len(line)
        offset += len(line)

    scan = "".join(masked)
    index = 0
    while index < len(scan):
        if scan[index] == "\\":
            masked[index] = " "
            if index + 1 < len(scan):
                masked[index + 1] = " "
            index += 2
            continue
        if scan[index] == "`":
            end = index
            while end < len(scan) and scan[end] == "`":
                end += 1
            delimiter = scan[index:end]
            closing = end
            while True:
                closing = scan.find(delimiter, closing)
                if closing < 0:
                    break
                before_matches = closing == 0 or scan[closing - 1] != "`"
                after = closing + len(delimiter)
                after_matches = after == len(scan) or scan[after] != "`"
                if before_matches and after_matches:
                    break
                closing = after
            if closing >= 0:
                masked[index : closing + len(delimiter)] = " " * (closing + len(delimiter) - index)
                index = closing + len(delimiter)
                continue
        index += 1

    return "".join(masked)


def _markdown_link_matches(
    text: str,
    source: PurePosixPath,
) -> list[MarkdownLink]:
    """Locate candidates, then bind each occurrence to a rendered link/image.

    The source scanner is deliberately not authoritative about code or comments.
    A second render with occurrence-specific URL suffixes establishes which
    destinations actually render. Literal examples cannot consume a live link's
    match, even when they contain the same URL.
    """
    scan = scan_candidates(text, source)
    links, syntax_errors = scan.links, scan.syntax_errors
    expected = checked_references(text, source)
    # Append markers, preserving each destination's original Markdown syntax.
    # These deterministic markers exist only in the probe, never in output.
    marker_base = "-dasc-policy-" + hashlib.sha256(text.encode()).hexdigest() + "-"
    edits: list[tuple[int, int, str]] = []
    probes: list[tuple[tuple[str, str], str, MarkdownLink | None]] = []
    for link in links:
        kind = "image" if link.label.startswith("!") else "link"
        marker = f"{marker_base}{len(probes)}"
        probes.append(LinkProbe((kind, unescape(link.destination)), marker, link))
        edits.append((link.destination_start, link.destination_end, link.destination + marker))
    for autolink in MARKDOWN_AUTOLINK_RE.finditer(text):
        if any(start < autolink.end() and autolink.start() < end for start, end, _ in edits):
            continue
        raw = autolink.group(0)[1:-1]
        key = ("link", raw if "://" in raw else f"mailto:{raw}")
        marker = f"{marker_base}{len(probes)}"
        probes.append(LinkProbe(key, marker, None))
        edits.append((autolink.start(), autolink.end(), f"[dasc-policy](<{key[1]}{marker}>)"))

    probe_text = text
    for start, end, replacement in sorted(edits, reverse=True):
        probe_text = probe_text[:start] + replacement + probe_text[end:]
    try:
        probe_parser = RenderedReferenceParser()
        probe_parser.feed(markdown.markdown(probe_text, extensions=MARKDOWN_POLICY_EXTENSIONS))
    except CollectionError:
        raise
    except Exception as exc:
        raise CollectionError(f"cannot locate Markdown links in {source}") from exc
    rendered_probes = Counter(probe_parser.references)

    confirmed: list[MarkdownLink] = []
    for key, marker, link in probes:
        if rendered_probes[(key[0], key[1] + marker)] == 1 and expected[key]:
            expected[key] -= 1
            if link is not None:
                confirmed.append(link)

    unsupported = sorted(
        key for key, count in expected.items() if count and not key[1].startswith("#fn")
    )
    if unsupported:
        if syntax_errors:
            raise CollectionError(syntax_errors[0])
        raise CollectionError(
            f"unsupported rendered Markdown link syntax in {source}: {unsupported[0][1]!r}"
        )
    return confirmed


def _has_reference_definition(text: str) -> bool:
    """Use MkDocs' Markdown parser family to recognize reference definitions."""
    try:
        parser = markdown.Markdown(extensions=MARKDOWN_POLICY_EXTENSIONS)
        parser.convert(text)
    except Exception as exc:
        raise CollectionError("cannot parse Markdown reference definitions") from exc
    return bool(parser.references)


def _rewrite(
    text: str, entry: Entry, selected: dict[tuple[str, str], Entry], checkout: Path
) -> str:
    edits = [
        RewriteEdit(
            match.destination_start,
            match.destination_end,
            rewrite_destination(match.label, match.destination, entry, selected, checkout),
        )
        for match in reversed(_markdown_link_matches(text, entry.source))
    ]
    rewritten = text
    for edit in edits:
        rewritten = rewritten[: edit.start] + edit.replacement + rewritten[edit.end :]
    return rewritten


@dataclass(frozen=True)
class CandidateScan:
    links: tuple[MarkdownLink, ...]
    syntax_errors: tuple[str, ...]


class LinkProbe(NamedTuple):
    key: tuple[str, str]
    marker: str
    link: MarkdownLink | None


@dataclass(frozen=True)
class RewriteEdit:
    start: int
    end: int
    replacement: str


def scan_candidates(text: str, source: PurePosixPath) -> CandidateScan:
    visible = text
    links: list[MarkdownLink] = []
    syntax_errors: list[str] = []
    index = 0
    while index < len(visible):
        start = index
        if visible[index] == "!" and index + 1 < len(visible) and visible[index + 1] == "[":
            index += 1
        if visible[index] != "[":
            index = start + 1
            continue
        cursor = index + 1
        label_depth = 1
        while cursor < len(visible) and label_depth:
            if visible[cursor] == "[":
                label_depth += 1
            elif visible[cursor] == "]":
                label_depth -= 1
            cursor += 1
        if label_depth or cursor >= len(visible) or visible[cursor] != "(":
            index = start + 1
            continue
        destination_start = cursor + 1
        if destination_start >= len(visible):
            index = start + 1
            continue
        if visible[destination_start] == "<":
            syntax_errors.append(f"angle-bracket link destinations are not allowed: {source}")
            index = start + 1
            continue
        if visible[destination_start].isspace():
            syntax_errors.append(f"empty or unsupported link destination in {source}")
            index = start + 1
            continue
        cursor = destination_start
        destination_end: int | None = None
        link_end: int | None = None
        parenthesis_depth = 0
        while cursor < len(visible):
            character = visible[cursor]
            if character in "\r\n":
                break
            if character == "(":
                parenthesis_depth += 1
            elif character == ")":
                if parenthesis_depth:
                    parenthesis_depth -= 1
                else:
                    destination_end = cursor
                    link_end = cursor + 1
                    break
            elif character.isspace() and parenthesis_depth == 0:
                destination_end = cursor
                title = re.match(
                    r"\s+(?:\"[^\"\r\n]*\"|'[^'\r\n]*')\s*\)",
                    visible[cursor:],
                )
                if title:
                    link_end = cursor + title.end()
                break
            cursor += 1
        if destination_end is None or link_end is None:
            syntax_errors.append(f"unsupported inline link syntax in {source}")
            index = start + 1
            continue
        destination = text[destination_start:destination_end]
        links.append(
            MarkdownLink(
                text[start : destination_start - 1],
                destination,
                destination_start,
                destination_end,
            )
        )
        index = link_end
    return CandidateScan(tuple(links), tuple(syntax_errors))


def checked_references(text: str, source: PurePosixPath):
    try:
        rendered = markdown.markdown(text, extensions=MARKDOWN_POLICY_EXTENSIONS)
        RenderedHTMLGuard(source).feed(rendered)
        parser = RenderedReferenceParser()
        parser.feed(rendered)
    except CollectionError:
        raise
    except Exception as exc:
        raise CollectionError(f"cannot parse Markdown links in {source}") from exc

    return Counter(parser.references)


def rewrite_destination(label: str, raw: str, entry: Entry, selected, checkout: Path) -> str:
    original = raw
    raw = unescape(raw)
    parsed = _split_link(raw, entry.source)
    if parsed.scheme in {"http", "https", "mailto"} or raw.startswith("#"):
        if label.startswith("!"):
            raise CollectionError(f"image is not approved: {raw}")
        return original
    if parsed.scheme or parsed.netloc or raw.startswith("/"):
        raise CollectionError(f"unsafe link {raw!r} in {entry.source}")
    if not parsed.path:
        if label.startswith("!"):
            raise CollectionError(f"image is not approved: {raw}")
        return original
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
    # Decode entities for URL interpretation, then encode syntax-sensitive
    # characters when emitting a changed destination. Preserve URI separators
    # and existing percent escapes in queries/fragments.
    query = quote(parsed.query, safe="/?:@!$&*+,;=-._~%")
    fragment = quote(parsed.fragment, safe="/?:@!$&*+,;=-._~%")
    suffix = (f"?{query}" if parsed.query else "") + (f"#{fragment}" if parsed.fragment else "")
    suffix = suffix.replace("&", "&amp;")
    return f"{target}{suffix}"
