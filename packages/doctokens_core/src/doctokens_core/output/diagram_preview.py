"""Shared reading budgets for saved diagram labels and explicit edges."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import islice

_NODE_LIMIT = 12
_LINK_LIMIT = 24
_TEXT_LIMIT = 1200


@dataclass(frozen=True)
class PreviewNode:
    id: int
    text: str
    truncated: bool


@dataclass(frozen=True)
class DiagramPreview:
    nodes: tuple[PreviewNode, ...]
    link_indices: tuple[int, ...]
    truncated: bool


def diagram_preview(labels: Sequence[tuple[int, str]], edges: Sequence[tuple[int, int]]) -> DiagramPreview:
    """Retain source order and IDs; never fabricate edges through hidden nodes."""
    nodes: list[PreviewNode] = []
    remaining = _TEXT_LIMIT
    for identifier, label in labels[:_NODE_LIMIT]:
        if label and not remaining:
            break
        clipped = len(label) > remaining
        value = label[: max(0, remaining - 1)] + "…" if clipped else label
        nodes.append(PreviewNode(identifier, value, clipped))
        remaining -= len(value)
    ids = {node.id for node in nodes}
    link_indices = tuple(islice((index for index, (start, end) in enumerate(edges) if start in ids and end in ids), _LINK_LIMIT))
    return DiagramPreview(
        tuple(nodes),
        link_indices,
        len(nodes) < len(labels) or len(link_indices) < len(edges) or any(node.truncated for node in nodes),
    )


def diagram_plain(labels: Sequence[str], resource_id: str | None, *, link_count: int = 0) -> str:
    """A readable label preview, with a lookup key only when content is omitted."""
    preview = diagram_preview(list(enumerate(labels, start=1)), [])
    marker = "SmartArt"
    if preview.truncated or link_count > _LINK_LIMIT:
        marker += f" id={resource_id} truncated" if resource_id else " truncated"
    body = "; ".join(node.text for node in preview.nodes if node.text.strip())
    return f"[{marker}: {body}]" if body else f"[{marker}]"
