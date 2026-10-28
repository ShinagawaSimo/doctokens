"""LaTeX reading text with nested revision ranges, independent of Office hosts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from xml.etree import ElementTree as ET

RevisionView = Literal["final", "original", "review"]
RevisionKind = Literal["inserted", "deleted"]
_MARKER = re.compile("\x00([0-9]+)([se])\x00")


@dataclass(frozen=True, slots=True)
class MathRevision:
    start: int
    end: int
    kind: RevisionKind
    author: str | None = None
    date: str | None = None


@dataclass(frozen=True, slots=True)
class MathResult:
    text: str
    revisions: tuple[MathRevision, ...] = ()


class RevisionCollector:
    """Keep markup through string composition without exposing internal markers.

    NUL cannot occur in source XML. Its internal markers survive LaTeX grouping
    and are removed once, after the complete expression has been composed.
    """

    def __init__(self) -> None:
        self._records: list[tuple[RevisionKind, str | None, str | None]] = []

    def wrap(self, value: str, kind: RevisionKind, author: str | None, date: str | None) -> str:
        if not value:
            return ""
        index = len(self._records)
        self._records.append((kind, author, date))
        return f"\x00{index}s\x00{value}\x00{index}e\x00"

    def finish(self, value: str) -> MathResult:
        parts: list[str] = []
        openings: dict[int, int] = {}
        opening_order: dict[int, int] = {}
        revisions: list[tuple[int, MathRevision]] = []
        length = offset = 0
        for match in _MARKER.finditer(value):
            fragment = value[offset : match.start()]
            parts.append(fragment)
            length += len(fragment)
            index = int(match[1])
            if match[2] == "s":
                openings[index] = length
                opening_order[index] = len(opening_order)
            else:
                kind, author, date = self._records[index]
                revisions.append((opening_order[index], MathRevision(openings.pop(index), length, kind, author, date)))
            offset = match.end()
        parts.append(value[offset:])
        # Outer intervals come before their nested intervals, even at equal starts.
        revisions.sort(key=lambda item: (item[1].start, -item[1].end, item[0]))
        return MathResult("".join(parts), tuple(item for _order, item in revisions))


def append_math_text(parent: ET.Element, text: str, revisions: tuple[MathRevision, ...] = ()) -> None:
    """Write one mixed-content equation; itertext remains the complete LaTeX."""
    stack: list[tuple[int, ET.Element]] = [(len(text), parent)]
    offset = 0

    def write(value: str) -> None:
        node = stack[-1][1]
        if len(node):
            node[-1].tail = (node[-1].tail or "") + value
        else:
            node.text = (node.text or "") + value

    for revision in revisions:
        while len(stack) > 1 and stack[-1][0] <= revision.start:
            end = stack[-1][0]
            write(text[offset:end])
            offset = end
            stack.pop()
        write(text[offset : revision.start])
        offset = revision.start
        child = ET.SubElement(stack[-1][1], "ins" if revision.kind == "inserted" else "del")
        if revision.author:
            child.set("author", revision.author)
        if revision.date:
            child.set("date", revision.date)
        stack.append((revision.end, child))
    while len(stack) > 1:
        end = stack[-1][0]
        write(text[offset:end])
        offset = end
        stack.pop()
    write(text[offset:])
