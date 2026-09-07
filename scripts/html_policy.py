"""HTML attribute checks shared by publication and built-site validation."""

from __future__ import annotations


def unique_attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str | None]:
    """Reject duplicates rather than disagreeing with browser first-value rules."""
    values: dict[str, str | None] = {}
    for name, value in attrs:
        folded = name.casefold()
        if folded in values:
            raise ValueError(f"duplicate HTML attribute: {folded}")
        values[folded] = value
    return values
