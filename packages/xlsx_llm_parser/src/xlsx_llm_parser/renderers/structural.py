"""HTML5 renderers for XLSX workbooks — all three densities."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..models import Cell, ParsedWorkbook, SheetInfo
from ._constants import (
    _CELL_BUDGET,
    _COL_BUDGET,
    _GRID_BOUND_SENTINEL,
    _HEAD_COLS,
    _HEAD_ROWS,
    _ROW_BUDGET,
    _TAIL_COLS,
    _TAIL_ROWS,
)

Density = str  # "plain" | "structural" | "semantic"


# ── Public API ──


def render_workbook(wb: ParsedWorkbook, *, density: Density = "structural") -> str:
    """Render a parsed workbook at the given density."""
    return "".join(iter_workbook(wb, density=density))


def iter_workbook(wb: ParsedWorkbook, *, density: Density = "structural") -> Iterator[str]:
    """Stream workbook rendering chunks — concatenation matches render_workbook."""
    yield f"density={density}\n"
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet, density, wb)


def render_range(
    wb: ParsedWorkbook,
    sheet: str,
    range_spec: str,
    *,
    density: Density = "structural",
) -> str:
    """Render cells within an A1-style range, e.g. ``"A1:H30"``.

    Returns the ``<grid ref=...>`` block for the matching sheet.
    Raises ``ValueError`` if the sheet is not found or the range is invalid.
    """
    sheet_info = _find_sheet(wb, sheet)
    start_col, start_row, end_col, end_row = _parse_range(range_spec)

    rows = sheet_info.get("rows", [])
    filtered = _filter_rows(rows, start_col, start_row, end_col, end_row)
    return _render_grid(filtered, density)


# ── Per-sheet rendering ──


def _render_sheet(sheet, density: Density, wb: ParsedWorkbook | None = None) -> Iterator[str]:
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

    if density == "plain":
        yield from _render_plain(rows)
    else:
        yield _render_grid(rows, density, wb)


# ── Plain text ──


def _render_plain(rows: list[list[Cell]]) -> Iterator[str]:
    """Tab-separated cell values, no coordinates."""
    for row_cells in rows:
        if not row_cells:
            continue
        texts = [cell["text"] for cell in row_cells]
        yield "\t".join(texts) + "\n"


# ── Grid rendering (structural / semantic) ──


def _render_grid(rows: list[list[Cell]], density: Density,
                 wb: ParsedWorkbook | None = None) -> str:
    if not rows:
        return ""

    all_rows = rows
    truncated = _should_truncate(rows)
    if truncated:
        all_rows = _head_tail_rows(rows)

    # Compute grid ref from ALL rows (full range), not the sampled subset
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

    ref = f"{_col_letter(min_col)}{min_row}:{_col_letter(max_col)}{max_row}"
    tag = f"<grid ref={ref}"
    if truncated:
        tag += " truncated"
    parts = [tag + ">\n"]

    for row_cells in all_rows:
        parts.append(_render_row(row_cells, min_col, density, wb))

    return "".join(parts)


def _render_row(row_cells: list[Cell], grid_min_col: int, density: Density,
                wb: ParsedWorkbook | None = None) -> str:
    actual_row = row_cells[0]["row"]
    parts = [f"<tr row={actual_row}>"]

    fmt_index = wb.get("fmt_index") if wb is not None else None

    next_col = grid_min_col
    for cell in row_cells:
        if cell.get("shadow"):
            next_col = cell["col"] + (cell.get("colspan", 1))
            continue

        c = cell["col"]
        tag_attrs = "td"
        if density == "semantic":
            if cell.get("colspan", 1) > 1:
                tag_attrs += f" colspan={cell['colspan']}"
            if cell.get("rowspan", 1) > 1:
                tag_attrs += f" rowspan={cell['rowspan']}"
            if cell.get("formula"):
                tag_attrs += f' formula="{escape(cell["formula"], quote=True)}"'
            if cell.get("formulaType"):
                tag_attrs += f" formulaType={escape(cell['formulaType'], quote=True)}"
            if cell.get("formulaRange"):
                tag_attrs += f" formulaRange={escape(cell['formulaRange'], quote=True)}"
            if fmt_index is not None and "style" in cell:
                style = fmt_index.style_attrs(cell["style"])
                if style:
                    tag_attrs += f" {style}"
        if c != next_col:
            tag_attrs += f" col={_col_letter(c)}"
        parts.append(f"<{tag_attrs}>")
        parts.append(escape(cell["text"]))
        next_col = c + (cell.get("colspan", 1))

    parts.append("\n")
    return "".join(parts)


# ── Truncation logic ──


def _should_truncate(rows: list[list[Cell]]) -> bool:
    cell_count = 0
    col_set: set[int] = set()
    for row_cells in rows:
        cell_count += len(row_cells)
        for cell in row_cells:
            col_set.add(cell["col"])
    return cell_count > _CELL_BUDGET or len(rows) > _ROW_BUDGET or len(col_set) > _COL_BUDGET


def _head_tail_rows(rows: list[list[Cell]]) -> list[list[Cell]]:
    """Keep head + tail rows. For wide tables, also restrict columns per row."""
    if len(rows) <= _HEAD_ROWS + _TAIL_ROWS:
        return rows

    # Compute column set for truncation
    col_set: set[int] = set()
    for row_cells in rows:
        for cell in row_cells:
            col_set.add(cell["col"])
    cols = sorted(col_set)

    should_truncate_cols = len(cols) > _COL_BUDGET
    keep_cols: set[int] = set()
    if should_truncate_cols:
        keep_cols = set(cols[:_HEAD_COLS]) | set(cols[-_TAIL_COLS:])
    else:
        keep_cols = set(cols)

    result: list[list[Cell]] = []
    for row_cells in rows[:_HEAD_ROWS]:
        if should_truncate_cols:
            row_cells = [c for c in row_cells if c["col"] in keep_cols]
        result.append(row_cells)

    for row_cells in rows[-_TAIL_ROWS:]:
        if should_truncate_cols:
            row_cells = [c for c in row_cells if c["col"] in keep_cols]
        result.append(row_cells)

    return result


# ── Helpers ──


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
