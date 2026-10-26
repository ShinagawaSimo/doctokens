"""Literal matching and bounded excerpts over format-owned text units."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..runtime.execution import checkpoint

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


class TextSearchCollector:
    """Bounded push-based matching, shared with iterable search traversal."""

    def __init__(self, query: str, options: TextSearchOptions) -> None:
        if not isinstance(query, str) or not query or len(query) > 4000:
            raise ValueError("query must contain 1 to 4000 characters")
        self.options = options
        self.pattern = re.compile(re.escape(query), 0 if options.case_sensitive else re.IGNORECASE)
        self.matches: list[TextMatch] = []
        self.seen: set[str] = set()
        self.skipped = 0
        self.complete = False
        self.next_offset: int | None = None
        self._checked = 0

    def consume(self, unit: TextUnit) -> bool:
        self._checked += 1
        if self._checked % 128 == 1:
            checkpoint("matching document text")
        if self.complete:
            return False
        if unit.group and unit.group in self.seen:
            return True
        match = self.pattern.search(unit.text)
        if match is None:
            return True
        if unit.group:
            self.seen.add(unit.group)
        if self.skipped < self.options.offset:
            self.skipped += 1
            return True
        if len(self.matches) == self.options.limit:
            self.next_offset = self.options.offset + len(self.matches)
            self.complete = True
            return False
        start = max(0, match.start() - self.options.context_before)
        end = min(len(unit.text), match.end() + self.options.context_after)
        excerpt = ("…" if start else "") + unit.text[start:end] + ("…" if end < len(unit.text) else "")
        self.matches.append(TextMatch(excerpt, dict(unit.locator)))
        return True

    def result(self) -> TextSearchResult:
        return TextSearchResult(tuple(self.matches), self.next_offset)


def search_text(units: Iterable[TextUnit], query: str, options: TextSearchOptions) -> TextSearchResult:
    collector = TextSearchCollector(query, options)
    for unit in units:
        if not collector.consume(unit):
            break
    return collector.result()
