"""Local rendered-document reference facts; never fetch external resources."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from html_policy import unique_attributes


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        values = unique_attributes(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("name"):
            self.ids.add(values["name"])
        for name in ("href", "src"):
            if values.get(name):
                self.references.append(values[name])


class DocumentIndex:
    def __init__(self, site: Path, base_path: str = "/"):
        self.site = site.resolve(strict=True)
        if not base_path.startswith("/") or not base_path.endswith("/"):
            raise ValueError("site base must begin and end with /")
        self.base_path = base_path
        self.pages: dict[Path, References] = {}

    def page(self, path: Path) -> References:
        path = path.resolve(strict=True)
        if not path.is_relative_to(self.site):
            raise ValueError("reference escapes site")
        if path not in self.pages:
            parser = References()
            parser.feed(path.read_text(encoding="utf-8"))
            self.pages[path] = parser
        return self.pages[path]

    def validate(self, page: Path, raw: str) -> None:
        parsed = urlsplit(raw)
        if parsed.scheme in {"http", "https", "mailto"} or raw == "javascript:void(0)":
            return
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"unsafe URL scheme in {page.relative_to(self.site)}: {raw}")
        if parsed.path.startswith("/"):
            if not parsed.path.startswith(self.base_path):
                raise ValueError(f"reference is outside the configured site base: {raw}")
            target = self.site / unquote(parsed.path.removeprefix(self.base_path), errors="strict")
        elif parsed.path:
            target = page.parent / unquote(parsed.path, errors="strict")
        else:
            target = page
        target = target.resolve()
        if not target.is_relative_to(self.site):
            raise ValueError(f"reference escapes site: {raw}")
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            raise ValueError(f"broken local reference in {page.relative_to(self.site)}: {raw}")
        if parsed.fragment and target.suffix.lower() in {".html", ".htm", ".svg"}:
            identifier = unquote(parsed.fragment, errors="strict")
            if identifier not in self.page(target).ids:
                raise ValueError(f"undefined local fragment in {page.relative_to(self.site)}: {raw}")
