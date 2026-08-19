"""Small shared models for collaborative annotations.

The anchor itself is format-specific: a text range in Word, a cell in Excel,
or a slide coordinate/shape in PowerPoint.  This module deliberately keeps
only the common conversation semantics here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypedDict


class AnnotationMention(TypedDict, total=False):
    """A person explicitly mentioned inside one threaded annotation."""

    person: str
    start: int
    length: int


class ThreadedAnnotation(TypedDict, total=False):
    """Common LLM-relevant fields of a threaded comment or reply."""

    id: str
    text: str
    author: str
    date: str
    parentId: str
    resolved: bool
    mentions: list[AnnotationMention]


def valid_parent_links(rows: Iterable[tuple[str, str | None]]) -> tuple[dict[str, str], set[str]]:
    """Return only parent links whose targets occur in the same annotation part.

    ``rows`` is consumed once.  The caller can surface the returned dangling
    IDs as format-local warnings without leaking package identifiers to output.
    """
    collected = list(rows)
    known_ids = {item_id for item_id, _parent_id in collected}
    links: dict[str, str] = {}
    dangling: set[str] = set()
    for item_id, parent_id in collected:
        if parent_id is None or parent_id == item_id:
            continue
        if parent_id in known_ids:
            links[item_id] = parent_id
        else:
            dangling.add(parent_id)
    return links, dangling
