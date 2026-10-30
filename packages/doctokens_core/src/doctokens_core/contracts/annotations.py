"""Small shared models for collaborative annotations.

The anchor itself is format-specific: a text range in Word, a cell in Excel,
or a slide coordinate/shape in PowerPoint.  This module deliberately keeps
only the common conversation semantics here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, TypedDict

AnnotationStatus = Literal["active", "resolved", "closed", "unknown"]


class AnnotationMention(TypedDict, total=False):
    """A person explicitly mentioned inside one threaded annotation."""

    person: str


class ThreadedAnnotation(TypedDict, total=False):
    """Common LLM-relevant fields of a threaded comment or reply."""

    id: str
    text: str
    author: str
    date: str
    parentId: str
    status: AnnotationStatus
    mentions: list[AnnotationMention]


def valid_parent_links(rows: Iterable[tuple[str, str | None]]) -> tuple[dict[str, str], set[str]]:
    """Return known, non-self, acyclic parents within one annotation part.

    ``rows`` is consumed once. The caller can report missing targets and invalid
    cycle members as format-local diagnostics without leaking source IDs to output.
    """
    collected = list(rows)
    known_ids = {item_id for item_id, _parent_id in collected}
    links: dict[str, str] = {}
    dangling: set[str] = set()
    for item_id, parent_id in collected:
        if parent_id is None:
            continue
        if parent_id == item_id:
            dangling.add(parent_id)
            continue
        if parent_id in known_ids:
            links[item_id] = parent_id
        else:
            dangling.add(parent_id)
    visited: set[str] = set()
    for item_id in list(links):
        path: list[str] = []
        positions: dict[str, int] = {}
        current = item_id
        while current in links and current not in visited:
            if current in positions:
                cycle = path[positions[current] :]
                dangling.update(cycle)
                for member in cycle:
                    links.pop(member)
                break
            positions[current] = len(path)
            path.append(current)
            current = links[current]
        visited.update(path)
    return links, dangling
