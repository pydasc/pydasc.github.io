#!/usr/bin/env python3
"""Validate built-site links, assets, paths, and presentation invariants."""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from html_references import DocumentIndex, References


PERSONAL_PATH = re.compile(r"/(?:Users|home)/[^\s<]+")
CSS_ROOT_URL = re.compile(r"url\(\s*(['\"]?)/")
SITE_BASE_PATH = "/"
REQUIRED_TOKENS = {
    "--dasc-sidebar-width": "300px",
    "--dasc-sidebar-bg": "#343131",
    "--dasc-sidebar-muted": "#9b9b9b",
    "--dasc-accent": "#2980b9",
    "--dasc-page-bg": "#fcfcfc",
    "--dasc-text": "#404040",
    "--dasc-content-max": "1000px",
}


def validate(site: Path, css: Path, base_path: str = "/") -> None:
    site = site.resolve(strict=True)
    stylesheet = css.read_text(encoding="utf-8")
    for token, value in REQUIRED_TOKENS.items():
        if not re.search(rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;", stylesheet):
            raise ValueError(f"missing CSS token {token}: {value}")
    if CSS_ROOT_URL.search(stylesheet) or PERSONAL_PATH.search(stylesheet):
        raise ValueError("unsafe root-relative URL or personal path in stylesheet")

    index = DocumentIndex(site, base_path)
    for html in sorted(site.rglob("*.html")):
        text = html.read_text(encoding="utf-8")
        if PERSONAL_PATH.search(text):
            raise ValueError(f"personal absolute path in {html.relative_to(site)}")
        for raw in index.page(html).references:
            index.validate(html, raw)

    home = (site / "index.html").read_text(encoding="utf-8")
    if "stylesheets/readthedocs.css" not in home:
        raise ValueError("home page does not load the local presentation stylesheet")
    for marker in (
        "data-dasc-drawer-control",
        'aria-controls="__drawer"',
        'aria-label="Open documentation navigation"',
    ):
        if marker not in home:
            raise ValueError(f"missing accessible mobile navigation marker: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--css", type=Path, required=True)
    parser.add_argument("--site-base-path", default="/")
    args = parser.parse_args()
    try:
        validate(args.site, args.css, args.site_base_path)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
