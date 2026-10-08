"""Explicit publication policies; changes require publication review."""

import re

EXPECTED = {
    "pydasc": "https://github.com/pydasc/pydasc",
    "dasc": "https://github.com/pydasc/dasc",
}

LEGACY_CONTRACT_REPOSITORIES = {
    "pydasc": "https://github.com/chongshikpark/pydasc",
    "dasc": "https://github.com/chongshikpark/dasc",
}

ALLOWED = {".md", ".png", ".jpg", ".jpeg", ".webp"}

MEDIA = {
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

MAX_FILE_BYTES = 5 * 1024 * 1024

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

SPDX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")

DOCUMENTATION_STATUSES = {
    "Draft",
    "Reviewed",
    "Reference",
    "Validated",
    "Unvalidated",
    "Superseded",
    "Released",
}

MARKDOWN_AUTOLINK_RE = re.compile(r"<(?:https?://[^<>\s]+|[^<>\s@]+@[^<>\s@]+)>")

BLOCKQUOTE_PREFIX_RE = re.compile(r"^ {0,3}>[ \t]?")

LIST_PREFIX_RE = re.compile(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+")

HTML_TAG_START_RE = re.compile(r"<\s*/?\s*[A-Za-z][A-Za-z0-9-]*")

ACTIVE_HTML_TAGS = {
    "a",
    "audio",
    "base",
    "button",
    "canvas",
    "embed",
    "form",
    "iframe",
    "img",
    "input",
    "link",
    "meta",
    "object",
    "option",
    "script",
    "select",
    "source",
    "style",
    "svg",
    "textarea",
    "track",
    "video",
}

UNSAFE_HTML_ATTRIBUTES = {
    "action",
    "archive",
    "background",
    "cite",
    "classid",
    "codebase",
    "data",
    "formaction",
    "href",
    "longdesc",
    "manifest",
    "ping",
    "poster",
    "profile",
    "src",
    "srcset",
    "style",
    "usemap",
    "xlink:href",
}

UNSAFE_ATTRIBUTION_RE = re.compile(r"(?:[\x00-\x1f<>\[\]]|--)")

FORBIDDEN = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+|AKIA[0-9A-Z]{16}|/(?:Users|home)/[^\s)`]+|https?://(?:localhost|127\.0\.0\.1|[^/\s]+\.internal)(?:[/\s)]|$))"
)

MARKDOWN_POLICY_EXTENSIONS = [
    "admonition",
    "attr_list",
    "footnotes",
    "md_in_html",
    "pymdownx.details",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.superfences",
    "toc",
]

RENDER_ALLOWED_ATTRIBUTES = {"a": {"href"}, "img": {"src"}}

RENDER_FORBIDDEN_TAGS = ACTIVE_HTML_TAGS - set(RENDER_ALLOWED_ATTRIBUTES)
