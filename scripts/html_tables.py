"""Preserve rendered bytes while wrapping supported, unnested table elements."""

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from html_policy import unique_attributes


@dataclass(frozen=True)
class TableSpan:
    start: int
    end: int
    number: int


class TableParser(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0]
        for index, character in enumerate(source):
            if character == "\n":
                self.offsets.append(index + 1)
        self.divs: list[bool] = []
        self.active: tuple[int, bool, int] | None = None
        self.count = 0
        self.spans: list[TableSpan] = []

    def source_offset(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        values = unique_attributes(attrs)
        if tag == "div":
            self.divs.append("dasc-table-scroll" in (values.get("class") or "").split())
        elif tag == "table":
            if self.active is not None:
                raise ValueError("nested tables are not supported by the documentation table hook")
            self.count += 1
            self.active = (self.source_offset(), any(self.divs), self.count)

    def handle_endtag(self, tag):
        if tag == "div" and self.divs:
            self.divs.pop()
        elif tag == "table":
            if self.active is None:
                raise ValueError("table closing tag has no matching opening tag")
            start, wrapped, number = self.active
            end = self.source.index(">", self.source_offset()) + 1
            if not wrapped:
                self.spans.append(TableSpan(start, end, number))
            self.active = None

    def handle_startendtag(self, tag, attrs):
        if tag == "table":
            raise ValueError("self-closing tables are not supported")
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def wrap_tables(content: str, title: str) -> str:
    parser = TableParser(content)
    parser.feed(content)
    parser.close()
    if parser.active is not None:
        raise ValueError("table opening tag has no matching closing tag")
    title = escape(title, quote=True)
    for span in reversed(parser.spans):
        label = f"Scrollable table: {title}, table {span.number}"
        wrapped = (
            '<div class="dasc-table-scroll" role="region" tabindex="0" '
            f'aria-label="{label}">\n{content[span.start : span.end]}\n</div>'
        )
        content = content[: span.start] + wrapped + content[span.end :]
    return content
