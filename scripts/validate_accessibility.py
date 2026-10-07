#!/usr/bin/env python3
"""Apply deterministic semantic-accessibility checks to built HTML pages."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path


class PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.headings: list[int] = []
        self.h1_count = 0
        self.images_without_alt = 0
        self.table_has_headers: list[bool] = []
        self.open_tables: list[int] = []
        self.tables_without_scroll_region = 0
        self.invalid_scroll_regions = 0
        self.scroll_region_depth = 0
        self.div_scroll_stack: list[bool] = []
        self.has_main = False
        self.has_title = False
        self.has_lang = False
        self.named_navs = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            if identifier in self.ids:
                self.duplicate_ids.add(identifier)
            self.ids.add(identifier)
        if tag == "html" and values.get("lang"):
            self.has_lang = True
        elif tag == "title":
            self.has_title = True
        elif tag == "main":
            self.has_main = True
        elif tag == "nav" and (values.get("aria-label") or values.get("aria-labelledby")):
            self.named_navs += 1
        elif tag == "div":
            classes = (values.get("class") or "").split()
            is_scroll_region = "dasc-table-scroll" in classes
            self.div_scroll_stack.append(is_scroll_region)
            if is_scroll_region:
                self.scroll_region_depth += 1
                if (
                    values.get("role") != "region"
                    or values.get("tabindex") != "0"
                    or not values.get("aria-label")
                ):
                    self.invalid_scroll_regions += 1
        elif tag == "img" and "alt" not in values:
            self.images_without_alt += 1
        elif tag == "table":
            self.open_tables.append(len(self.table_has_headers))
            self.table_has_headers.append(False)
            if not self.scroll_region_depth:
                self.tables_without_scroll_region += 1
        elif tag == "th" and self.open_tables:
            self.table_has_headers[self.open_tables[-1]] = True
        elif len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            level = int(tag[1])
            self.headings.append(level)
            self.h1_count += level == 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.open_tables:
            self.open_tables.pop()
        elif tag == "div" and self.div_scroll_stack:
            if self.div_scroll_stack.pop():
                self.scroll_region_depth -= 1


def validate(site: Path) -> None:
    site = site.resolve(strict=True)
    pages = sorted(site.rglob("*.html"))
    if not pages:
        raise ValueError("site contains no HTML pages")
    for page in pages:
        audit = PageAudit()
        audit.feed(page.read_text(encoding="utf-8"))
        relative = page.relative_to(site)
        failures: list[str] = []
        if not audit.has_lang:
            failures.append("missing document language")
        if not audit.has_title:
            failures.append("missing title")
        if not audit.has_main:
            failures.append("missing main landmark")
        if audit.h1_count != 1:
            failures.append(f"expected one h1, found {audit.h1_count}")
        if any(current > previous + 1 for previous, current in zip(audit.headings, audit.headings[1:])):
            failures.append("heading level is skipped")
        if audit.images_without_alt:
            failures.append(f"{audit.images_without_alt} image(s) lack alt attributes")
        tables_without_headers = audit.table_has_headers.count(False)
        if tables_without_headers:
            failures.append(f"{tables_without_headers} table(s) have no header cells")
        if audit.tables_without_scroll_region:
            failures.append(
                f"{audit.tables_without_scroll_region} table(s) lack keyboard-scrollable regions"
            )
        if audit.invalid_scroll_regions:
            failures.append(
                f"{audit.invalid_scroll_regions} table region(s) lack required accessibility attributes"
            )
        if audit.duplicate_ids:
            failures.append(f"duplicate ids: {sorted(audit.duplicate_ids)}")
        if not audit.named_navs:
            failures.append("navigation landmarks lack accessible names")
        if failures:
            raise ValueError(f"{relative}: {'; '.join(failures)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.site)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
