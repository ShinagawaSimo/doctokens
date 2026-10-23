"""Literal matching and bounded excerpts over format-owned text units."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

Locator = dict[str, str | int]


@dataclass(frozen=True)
class TextSearchOptions:
    case_sensitive: bool = True
    offset: int = 0
    limit: int = 20
    context_before: int = 80
    context_after: int = 80

    def __post_init__(self) -> None:
        if not isinstance(self.case_sensitive, bool):
            raise ValueError("case_sensitive must be boolean")
        for name, minimum, maximum in (
            ("offset", 0, None),
            ("limit", 1, 200),
            ("context_before", 0, 4000),
            ("context_after", 0, 4000),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < minimum
                or (maximum is not None and value > maximum)
            ):
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True)
class TextUnit:
    text: str
    locator: Locator
    group: str = ""


@dataclass(frozen=True)
class TextMatch:
    text: str
    locator: Locator


@dataclass(frozen=True)
class TextSearchResult:
    matches: tuple[TextMatch, ...] = field(default_factory=tuple)
    next_offset: int | None = None


def search_text(units: Iterable[TextUnit], query: str, options: TextSearchOptions) -> TextSearchResult:
    if not isinstance(query, str) or not query or len(query) > 4000:
        raise ValueError("query must contain 1 to 4000 characters")
    pattern = re.compile(re.escape(query), 0 if options.case_sensitive else re.IGNORECASE)
    matches: list[TextMatch] = []
    seen: set[str] = set()
    skipped = 0
    for unit in units:
        if unit.group and unit.group in seen:
            continue
        match = pattern.search(unit.text)
        if match is None:
            continue
        if unit.group:
            seen.add(unit.group)
        if skipped < options.offset:
            skipped += 1
            continue
        if len(matches) == options.limit:
            return TextSearchResult(tuple(matches), options.offset + len(matches))
        start = max(0, match.start() - options.context_before)
        end = min(len(unit.text), match.end() + options.context_after)
        excerpt = ("…" if start else "") + unit.text[start:end] + ("…" if end < len(unit.text) else "")
        matches.append(TextMatch(excerpt, dict(unit.locator)))
    return TextSearchResult(tuple(matches))
