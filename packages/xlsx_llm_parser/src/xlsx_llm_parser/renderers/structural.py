"""Structural HTML5 renderer for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..models import ParsedWorkbook
from ._constants import _GRID_BOUND_SENTINEL


def render_workbook(wb: ParsedWorkbook) -> str:
    """Render a parsed workbook as structural HTML5."""
    return "".join(iter_workbook(wb))


def iter_workbook(wb: ParsedWorkbook) -> Iterator[str]:
    """Stream workbook rendering chunks."""
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet)


def _render_sheet(sheet) -> Iterator[str]:
    """Render one sheet with grid and rows."""
    name = sheet["name"]
    state = sheet.get("state", "visible")
    kind = sheet.get("kind", "worksheet")

    # Chartsheet: special tag, no grid content
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

    # Compute actual grid ref from cell positions (do not trust <dimension>)
    min_col = _GRID_BOUND_SENTINEL
    max_col = 0
    min_row = _GRID_BOUND_SENTINEL
    max_row = 0
    for row_cells in rows:
        for cell in row_cells:
            c = cell["col"]
            r = cell["row"]
            if c < min_col:
                min_col = c
            if c > max_col:
                max_col = c
            if r < min_row:
                min_row = r
            if r > max_row:
                max_row = r

    ref = f"{_col_letter(min_col)}{min_row}:{_col_letter(max_col)}{max_row}"
    yield f"<grid ref={ref}>\n"

    next_row = min_row
    for row_cells in rows:
        if not row_cells:
            continue
        actual_row = row_cells[0]["row"]
        tr_parts = ["<tr>"]
        if actual_row != next_row:
            tr_parts = [f"<tr row={actual_row}>"]
        next_row = actual_row + 1

        next_col = min_col
        for cell in row_cells:
            c = cell["col"]
            tag = "td"
            if c != next_col:
                tr_parts.append(f"<{tag} col={_col_letter(c)}>")
            else:
                tr_parts.append(f"<{tag}>")
            tr_parts.append(escape(cell["text"]))
            next_col = c + 1

        yield "".join(tr_parts) + "\n"


def _col_letter(col: int) -> str:
    """Convert 1-based column number to A-Z letter(s)."""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(ord("A") + rem) + result
    return result
