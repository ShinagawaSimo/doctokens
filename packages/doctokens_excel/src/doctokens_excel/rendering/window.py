"""Explicit source ranges and row-preserving default reading windows."""

from __future__ import annotations

from dataclasses import dataclass

from .._utils import col_letter
from ..models import Cell, SheetInfo
from ._constants import _CELL_BUDGET
from .reading_rows import reading_rows
from .selection import filter_rows, parse_range


def cell_bounds(rows: list[list[Cell]]) -> tuple[int, int, int, int] | None:
    bounds: tuple[int, int, int, int] | None = None
    for row in rows:
        for cell in row:
            col, number = cell["col"], cell["row"]
            if bounds is None:
                bounds = col, number, col, number
            else:
                bounds = min(bounds[0], col), min(bounds[1], number), max(bounds[2], col), max(bounds[3], number)
    return bounds


def range_ref(bounds: tuple[int, int, int, int] | None) -> str | None:
    if bounds is None:
        return None
    left, top, right, bottom = bounds
    return f"{col_letter(left)}{top}:{col_letter(right)}{bottom}"


@dataclass(frozen=True)
class ReadingWindow:
    rows: list[list[Cell]]
    metadata: dict[str, object]
    next_row: int | None

    @property
    def truncated(self) -> bool:
        return self.next_row is not None


def reading_window(
    sheet: SheetInfo,
    density: str,
    *,
    range_spec: str | None = None,
    rows: list[list[Cell]] | None = None,
) -> ReadingWindow:
    """Count emitted cells, finish the threshold row, and never split a row."""
    requested = parse_range(range_spec) if range_spec is not None else None
    exact = requested is not None or rows is not None
    if rows is None:
        source = sheet.get("rows", [])
        rows = filter_rows(source, *requested) if requested is not None else reading_rows(source)
    emitted: list[list[Cell]] = []
    count = 0
    next_row = None if exact else sheet.get("preview_next_row")
    hidden = sheet.get("hidden_cols", [])
    for row in rows:
        if not row:
            continue
        if not exact and count >= _CELL_BUDGET:
            next_row = row[0]["row"]
            break
        emitted.append(row)
        if density == "plain":
            count += sum(not any(first <= cell["col"] <= last for first, last in hidden) for cell in row)
        else:
            count += sum(not cell.get("shadow", False) for cell in row)
    bounds = cell_bounds(emitted)
    metadata: dict[str, object] = {
        "sheet": sheet["name"],
        "requested_range": range_spec,
        "returned_range": range_ref(bounds),
        "cell_count": count,
        "cell_limit": None if exact else _CELL_BUDGET,
        "truncated": next_row is not None,
        "next_row": next_row,
        "next_cell": f"A{next_row}" if next_row is not None else None,
        "merged_ranges": _crossing_merges(sheet, requested or bounds),
    }
    return ReadingWindow(emitted, metadata, next_row)


def _crossing_merges(sheet: SheetInfo, bounds: tuple[int, int, int, int] | None) -> list[dict[str, object]]:
    """Expose crossing anchors without expanding or filling the selected grid."""
    if bounds is None:
        return []
    left, top, right, bottom = bounds
    result: list[dict[str, object]] = []
    for ref in sheet.get("merge_refs", []):
        try:
            x1, y1, x2, y2 = parse_range(ref)
        except ValueError:
            continue
        intersects = x1 <= right and left <= x2 and y1 <= bottom and top <= y2
        contained = left <= x1 <= x2 <= right and top <= y1 <= y2 <= bottom
        if intersects and not contained:
            result.append(
                {
                    "ref": ref,
                    "anchor": f"{col_letter(x1)}{y1}",
                    "anchor_in_range": left <= x1 <= right and top <= y1 <= bottom,
                }
            )
    return result
