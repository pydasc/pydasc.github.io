#!/usr/bin/env python3
"""Validate DASC physics equation anchors, citation keys, and safe paths."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown
from collect_docs import MARKDOWN_POLICY_EXTENSIONS
from html_references import References


EQUATION_ID = re.compile(r'\bid="(eq-[a-z0-9-]+)"')
ANCHOR_LINK = re.compile(r"\[[^]]+\]\(([^)]+#eq-[a-z0-9-]+)\)")
FOOTNOTE_MARK = re.compile(r"\[\^([A-Za-z0-9_-]+)\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([A-Za-z0-9_-]+)\]:", re.MULTILINE)
LOCAL_PATH = re.compile(r"/(?:Users|home)/[^\s)<]+")
UNSUPPORTED_TEX = re.compile(r"\\(?:ref|eqref|cite)\{|\$\$|\\\[|\\\]")
MISPLACED_MEASURE_EXPONENT = re.compile(
    r"<mi>d</mi><msup><mi(?:\s+[^>]*)?>(?:V|r|k)</mi><mn>3</mn></msup>"
)
MATH_GROUP = re.compile(
    r'<div\s+id="eq-[a-z0-9-]+"\s+class="dasc-equation"\s+'
    r'role="group"\s+aria-label="[^"]+">\s*<math\s+display="block">',
    re.MULTILINE,
)


def validate(docs: Path) -> None:
    docs = docs.resolve(strict=True)
    pages = sorted(docs.glob("dasc-*.md"))
    if not pages:
        raise ValueError("no authored DASC pages found")
    equations: dict[tuple[Path, str], None] = {}
    texts: dict[Path, str] = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        texts[page] = text
        if LOCAL_PATH.search(text) or UNSUPPORTED_TEX.search(text):
            raise ValueError(f"unsafe path or unsupported TeX reference in {page.name}")
        if MISPLACED_MEASURE_EXPONENT.search(text):
            raise ValueError(
                f"three-dimensional measure exponent is attached to the variable in {page.name}"
            )
        ids = EQUATION_ID.findall(text)
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate equation id in {page.name}")
        if text.count('<math display="block">') != len(MATH_GROUP.findall(text)):
            raise ValueError(f"display math lacks an accessible equation group in {page.name}")
        for identifier in ids:
            equations[(page, identifier)] = None
        defs = set(FOOTNOTE_DEF.findall(text))
        marks = FOOTNOTE_MARK.findall(text)
        refs = {key for key in marks if marks.count(key) > (1 if key in defs else 0)}
        if refs != defs:
            raise ValueError(
                f"citation-footnote mismatch in {page.name}: "
                f"missing={sorted(refs - defs)}, unused={sorted(defs - refs)}"
            )
    for page, text in texts.items():
        rendered = References()
        rendered.feed(markdown.markdown(text, extensions=MARKDOWN_POLICY_EXTENSIONS))
        for raw in rendered.references:
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc or not parsed.fragment.startswith("eq-"):
                continue
            identifier = unquote(parsed.fragment)
            target = page if not parsed.path else (page.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(docs) or (target, identifier) not in equations:
                raise ValueError(f"undefined equation reference in {page.name}: {raw}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.docs)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
