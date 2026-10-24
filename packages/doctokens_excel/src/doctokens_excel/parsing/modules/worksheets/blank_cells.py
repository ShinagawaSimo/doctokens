"""Preserve blank association anchors without materializing empty rectangles."""

from __future__ import annotations

from collections.abc import Iterable

from ...._utils import parse_ref
from ....models import Cell


def preserve_blank_ranges(rows: list[list[Cell]], refs: Iterable[str]) -> None:
    """Mark existing candidates in source ranges; no formula or rule evaluation."""
    bounds: list[tuple[int, int, int, int]] = []
    for ref in refs:
        for area in ref.split():
            first, _, last = area.replace("$", "").partition(":")
            try:
                left, top = parse_ref(first)
                right, bottom = parse_ref(last or first)
            except (ValueError, IndexError):
                continue
            bounds.append((left, top, right, bottom))
    if not bounds:
        return
    for row in rows:
        for cell in row:
            if cell.get("blankCandidate") and any(
                left <= cell["col"] <= right and top <= cell["row"] <= bottom for left, top, right, bottom in bounds
            ):
                cell.pop("blankCandidate")
