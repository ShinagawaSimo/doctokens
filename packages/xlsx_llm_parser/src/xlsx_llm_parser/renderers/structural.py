"""Structural HTML5 renderer for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..models import Cell, ParsedWorkbook, SheetInfo
from ._constants import _GRID_BOUND_SENTINEL


def render_workbook(wb: ParsedWorkbook) -> str:
    """Render a parsed workbook as structural HTML5."""
    return "".join(iter_workbook(wb))


def iter_workbook(wb: ParsedWorkbook) -> Iterator[str]:
    """Stream workbook rendering chunks."""
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet)


def render_range(
    wb: ParsedWorkbook,
    sheet: str,
    range_spec: str,
) -> str:
    """Render cells within an A1-style range, e.g. ``"A1:H30"``.

    Returns only the ``<grid ref=...>`` block for the matching sheet.
    Raises ``ValueError`` if the sheet is not found or the range is invalid.
    """
    sheet_info = _find_sheet(wb, sheet)
    start_col, start_row, end_col, end_row = _parse_range(range_spec)

    rows = sheet_info.get("rows", [])
    filtered = _filter_rows(rows, start_col, start_row, end_col, end_row)
    return _render_grid(filtered)


def _find_sheet(wb: ParsedWorkbook, name: str) -> SheetInfo:
    for s in wb["sheets"]:
        if s["name"] == name:
            return s
    raise ValueError(f"Sheet {name!r} not found")


def _parse_range(spec: str) -> tuple[int, int, int, int]:
    """Parse ``A1:H30`` into (start_col, start_row, end_col, end_row)."""
    if ":" not in spec:
        raise ValueError(f"Invalid range {spec!r}: expected 'A1:B2' format")
    start_ref, end_ref = spec.split(":", 1)
    sc, sr = _parse_ref(start_ref)
    ec, er = _parse_ref(end_ref)
    return sc, sr, ec, er


def _filter_rows(
    rows: list[list[Cell]],
    start_col: int,
    start_row: int,
    end_col: int,
    end_row: int,
) -> list[list[Cell]]:
    """Keep only cells within the requested A1 range."""
    result: list[list[Cell]] = []
    for row_cells in rows:
        kept = [
            c
            for c in row_cells
            if start_col <= c["col"] <= end_col and start_row <= c["row"] <= end_row
        ]
        if kept:
            result.append(kept)
    return result


def _render_grid(rows: list[list[Cell]]) -> str:
    """Render a filtered set of rows as a ``<grid>`` block."""
    if not rows:
        return ""

    min_col = _GRID_BOUND_SENTINEL
    max_col = 0
    min_row = _GRID_BOUND_SENTINEL
    max_row = 0
    for row_cells in rows:
        for cell in row_cells:
            if cell["col"] < min_col:
                min_col = cell["col"]
            if cell["col"] > max_col:
                max_col = cell["col"]
            if cell["row"] < min_row:
                min_row = cell["row"]
            if cell["row"] > max_row:
                max_row = cell["row"]

    parts = [f"<grid ref={_col_letter(min_col)}{min_row}:{_col_letter(max_col)}{max_row}>\n"]

    for row_cells in rows:
        actual_row = row_cells[0]["row"]
        parts.append(f"<tr row={actual_row}>")

        next_col = min_col
        for cell in row_cells:
            c = cell["col"]
            if c != next_col:
                parts.append(f"<td col={_col_letter(c)}>")
            else:
                parts.append("<td>")
            parts.append(escape(cell["text"]))
            next_col = c + 1

        parts.append("\n")

    return "".join(parts)


# ── Sheet rendering ──


def _render_sheet(sheet) -> Iterator[str]:
    """Render one sheet with grid and rows."""
    name = sheet["name"]
    state = sheet.get("state", "visible")
    kind = sheet.get("kind", "worksheet")

    if kind == "chartsheet":
        yield f"<chartsheet name={escape(name, quote=True)}>\n"
        return

    attrs = f"name={escape(name, quote=True)}"
    if state == "hidden":
        attrs += " hidden"
    elif state == "veryHidden":
        attrs += " veryHidden"
    yield f"<sheet {attrs}>\n"

    rows = sheet.get("rows", [])
    if not rows:
        return

    yield _render_grid(rows)


# ── Helpers ──


def _col_letter(col: int) -> str:
    """Convert 1-based column number to A-Z letter(s)."""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def _parse_ref(ref: str) -> tuple[int, int]:
    """Parse an A1-style reference into (col, row) as 1-based integers."""
    col_str = ""
    row_str = ""
    for ch in ref:
        if ch.isalpha():
            col_str += ch
        else:
            row_str += ch
    col = 0
    for ch in col_str.upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    row = int(row_str) if row_str else 0
    return col, row
