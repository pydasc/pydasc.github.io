#!/usr/bin/env python3
"""Apply deterministic semantic-accessibility checks to built HTML pages."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path

from html_policy import unique_attributes


class PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.headings: list[int] = []
        self.h1_count = 0
        self.images_without_alt = 0
        self.tables = 0
        self.table_headers: list[int] = []
        self.table_stack: list[int] = []
        self.tables_without_scroll_region = 0
        self.invalid_scroll_regions = 0
        self.in_table = 0
        self.scroll_region_depth = 0
        self.div_scroll_stack: list[bool] = []
        self.has_main = False
        self.has_title = False
        self.has_lang = False
        self.navigation: list[dict[str, str | None]] = []
        self.element_stack: list[tuple[str, str | None]] = []
        self.id_text: dict[str, list[str]] = {}
        self.title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = unique_attributes(attrs)
        void = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
        if tag not in void:
            self.element_stack.append((tag, values.get("id")))
        identifier = values.get("id")
        if identifier:
            if identifier in self.ids:
                self.duplicate_ids.add(identifier)
            self.ids.add(identifier)
            self.id_text.setdefault(identifier, [])
        if tag == "html" and values.get("lang"):
            self.has_lang = True
        elif tag == "title":
            self.has_title = True
        elif tag == "main":
            self.has_main = True
        elif tag == "nav":
            self.navigation.append(values)
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
            self.tables += 1
            self.in_table += 1
            self.table_stack.append(len(self.table_headers))
            self.table_headers.append(0)
            if not self.scroll_region_depth:
                self.tables_without_scroll_region += 1
        elif tag == "th" and self.table_stack:
            self.table_headers[self.table_stack[-1]] += 1
        elif len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            level = int(tag[1])
            self.headings.append(level)
            self.h1_count += level == 1

    def handle_data(self, data: str) -> None:
        for tag, identifier in self.element_stack:
            if identifier:
                self.id_text[identifier].append(data)
            if tag == "title":
                self.title_text.append(data)

    def unnamed_navigation(self) -> list[int]:
        failures = []
        for number, values in enumerate(self.navigation, 1):
            references = (values.get("aria-labelledby") or "").split()
            if references:
                named = all("".join(self.id_text.get(ref, [])).strip() for ref in references)
            else:
                named = bool((values.get("aria-label") or "").strip())
            if not named:
                failures.append(number)
        return failures

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.element_stack) - 1, -1, -1):
            if self.element_stack[index][0] == tag:
                del self.element_stack[index:]
                break
        if tag == "table" and self.table_stack:
            self.table_stack.pop()
            self.in_table -= 1
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
        if not audit.has_title or not "".join(audit.title_text).strip():
            failures.append("missing or empty title")
        if not audit.has_main:
            failures.append("missing main landmark")
        if audit.h1_count != 1:
            failures.append(f"expected one h1, found {audit.h1_count}")
        if any(
            current > previous + 1 for previous, current in zip(audit.headings, audit.headings[1:])
        ):
            failures.append("heading level is skipped")
        if audit.images_without_alt:
            failures.append(f"{audit.images_without_alt} image(s) lack alt attributes")
        for number, headers in enumerate(audit.table_headers, 1):
            if not headers:
                failures.append(f"table {number} markup has no header cells")
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
        unnamed = audit.unnamed_navigation()
        if not audit.navigation or unnamed:
            failures.append(f"navigation landmarks lack accessible names: {unnamed}")
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
