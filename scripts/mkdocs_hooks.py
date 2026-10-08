"""Small deterministic transformations applied to rendered documentation pages."""

from __future__ import annotations

import html
import re
from typing import Any


TABLE = re.compile(r"<table(?:\s[^>]*)?>.*?</table>", re.DOTALL)


def on_page_content(content: str, page: Any, **_: Any) -> str:
    """Wrap tables in named, keyboard-scrollable regions."""

    title = html.escape(str(page.title), quote=True)
    table_number = 0

    def wrap(match: re.Match[str]) -> str:
        nonlocal table_number
        table_number += 1
        label = f"Scrollable table: {title}, table {table_number}"
        return (
            '<div class="dasc-table-scroll" role="region" tabindex="0" '
            f'aria-label="{label}">\n{match.group(0)}\n</div>'
        )

    return TABLE.sub(wrap, content)


def on_env(env: Any, **_: Any) -> Any:
    """Name Material index-section landmarks without copying its nav template.

    Material 9.7.7 points these landmarks at an icon-only toggle. Use the
    existing text-bearing section title instead; fail visibly on theme drift.
    """
    from jinja2 import ChoiceLoader, DictLoader

    if getattr(env, "_dasc_nav_labels", False):
        return env
    name = "partials/nav-item.html"
    source, _, _ = env.loader.get_source(env, name)
    replacements = {
        'aria-labelledby="{{ path }}_label"': 'aria-labelledby="{{ path }}_title"',
        '<label class="md-nav__title" for="{{ path }}">': '<label class="md-nav__title" for="{{ path }}" id="{{ path }}_title">',
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise ValueError("Material navigation template changed; review accessible labels")
        source = source.replace(before, after)
    env.loader = ChoiceLoader([DictLoader({name: source}), env.loader])
    env._dasc_nav_labels = True
    return env
