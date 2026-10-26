"""Selection helpers shared by XLSX render and query entry points."""

from __future__ import annotations

import re

from ..model.coordinates import parse_ref
from ..model.workbook import Cell, ParsedWorkbook, SheetInfo

MAX_COLUMN = 16_384
MAX_ROW = 1_048_576
_CELL_REF = r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)"


def find_sheet(workbook: ParsedWorkbook, name: str) -> SheetInfo:
    """Return a worksheet by its display name."""
    for sheet in workbook["sheets"]:
        if sheet["name"] == name:
            return sheet
    raise ValueError(f"Sheet {name!r} not found")


def parse_range(spec: str) -> tuple[int, int, int, int]:
    """Parse a rectangle, inclusive whole rows, or one cell in one sheet."""
    if rows := re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)", spec):
        start_col, end_col = 1, MAX_COLUMN
        start_row, end_row = map(int, rows.groups())
    elif cells := re.fullmatch(rf"{_CELL_REF}(?::{_CELL_REF})?", spec):
        first_col, first_row, last_col, last_row = cells.groups()
        start_col, start_row = parse_ref(first_col + first_row)
        end_col, end_row = parse_ref((last_col or first_col) + (last_row or first_row))
    else:
        raise ValueError(f"Invalid range {spec!r}: expected A1:H20, 10:20, or A1 within one sheet")
    if not (1 <= start_col <= end_col <= MAX_COLUMN and 1 <= start_row <= end_row <= MAX_ROW):
        raise ValueError(f"Invalid range {spec!r}: endpoints must be ordered within A1:XFD1048576")
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
