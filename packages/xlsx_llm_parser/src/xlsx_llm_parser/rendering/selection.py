"""Selection helpers shared by XLSX render and query entry points."""

from __future__ import annotations

from .._utils import parse_ref
from ..models import Cell, ParsedWorkbook, SheetInfo


def find_sheet(workbook: ParsedWorkbook, name: str) -> SheetInfo:
    """Return a worksheet by its display name."""
    for sheet in workbook["sheets"]:
        if sheet["name"] == name:
            return sheet
    raise ValueError(f"Sheet {name!r} not found")


def parse_range(spec: str) -> tuple[int, int, int, int]:
    """Parse ``A1:H30`` into ``(start_col, start_row, end_col, end_row)``."""
    if ":" not in spec:
        raise ValueError(f"Invalid range {spec!r}: expected 'A1:B2' format")
    start_ref, end_ref = spec.split(":", 1)
    start_col, start_row = parse_ref(start_ref)
    end_col, end_row = parse_ref(end_ref)
    return start_col, start_row, end_col, end_row


def filter_rows(
    rows: list[list[Cell]],
    start_col: int,
    start_row: int,
    end_col: int,
    end_row: int,
) -> list[list[Cell]]:
    """Return cells within an explicit A1 range without filling blank cells."""
    selected: list[list[Cell]] = []
    for row in rows:
        cells = [cell for cell in row if start_col <= cell["col"] <= end_col and start_row <= cell["row"] <= end_row]
        if cells:
            selected.append(cells)
    return selected


__all__ = ["filter_rows", "find_sheet", "parse_range"]
