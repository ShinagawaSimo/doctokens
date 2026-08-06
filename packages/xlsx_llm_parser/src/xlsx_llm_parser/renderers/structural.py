"""HTML5 renderers for XLSX workbooks — all three densities."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ..models import Cell, ParsedWorkbook, SheetInfo
from ._constants import (
    _CELL_BUDGET,
    _COL_BUDGET,
    _GRID_BOUND_SENTINEL,
    _ROW_BUDGET,
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

    if density != "plain":
        # Hidden column ranges from <cols> — output before <grid>
        hidden_cols = sheet.get("hidden_cols")
        if hidden_cols:
            for cmin, cmax in hidden_cols:
                col_range = _col_letter(cmin) if cmin == cmax else f"{_col_letter(cmin)}:{_col_letter(cmax)}"
                yield f"<columns ref={col_range} hidden>\n"

    if density == "semantic" and sheet.get("sheet_protection"):
        yield "<sheetProtection/>\n"

    # Table summaries before grid
    for t in sheet.get("tables", []):
        attrs = f"id={t['id']} name={escape(t['name'], quote=True)} ref={t['ref']}"
        if density == "semantic" and t.get("columns"):
            cols = ",".join(t["columns"])
            attrs += f' cols="{escape(cols, quote=True)}"'
        if density == "semantic" and t.get("totalsRow"):
            attrs += " totalsRow"
        yield f"<table {attrs}>\n"

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

    # Compute grid ref from all rows
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
    if _should_truncate(rows):
        # Large sheet: only show the range, no data rows
        return tag + " truncated>\n"

    parts = [tag + ">\n"]
    comments: dict[tuple[int, int], tuple[str, str, str]] = {}  # (col,row) → (ref, author, text)
    for row_cells in rows:
        parts.append(_render_row(row_cells, min_col, density, wb, comments))

    # Output comment blocks after the grid
    for idx, ((_col, _row), (ref, author, text)) in enumerate(sorted(comments.items(), key=lambda x: (x[0][1], x[0][0]))):
        attrs = f'id=comment{idx} cell="{escape(ref, quote=True)}"'
        if author:
            attrs += f" author={escape(author, quote=True)}"
        parts.append(f"<comment {attrs}>{escape(text)}\n")

    return "".join(parts)


def _render_row(row_cells: list[Cell], grid_min_col: int, density: Density,
                wb: ParsedWorkbook | None = None,
                comments: dict[tuple[int, int], tuple[str, str, str]] | None = None) -> str:
    actual_row = row_cells[0]["row"]
    first_cell = row_cells[0]
    row_hidden = " hidden" if first_cell.get("hidden") else ""
    parts = [f"<tr row={actual_row}{row_hidden}"]
    if density == "semantic" and first_cell.get("outlineLevel"):
        parts.append(f" outlineLevel={first_cell['outlineLevel']}")
        if first_cell.get("collapsed"):
            parts.append(" collapsed")
    parts.append(">")

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
            if cell.get("spillRange"):
                tag_attrs += f" spillRange={escape(cell['spillRange'], quote=True)}"
            if cell.get("spillFrom"):
                tag_attrs += f' spillFrom="{escape(cell["spillFrom"], quote=True)}"'
            if fmt_index is not None and "style" in cell:
                style = fmt_index.style_attrs(cell["style"])
                if style:
                    tag_attrs += f" {style}"
                prot = fmt_index.protection_attrs(cell["style"])
                if prot:
                    tag_attrs += f" {prot}"
        if c != next_col:
            tag_attrs += f" col={_col_letter(c)}"
        parts.append(f"<{tag_attrs}>")
        body = _render_rich_text(cell["rich"]) if density == "semantic" and cell.get("rich") else escape(cell["text"])
        if cell.get("hyperlink"):
            body = f'<a href="{escape(cell["hyperlink"], quote=True)}">{body}</a>'
        # Inline comment reference + register for post-grid output
        if cell.get("comment") and comments is not None:
            cid = len(comments)
            body += f"<commentref id=comment{cid}/>"
            comments[(cell["col"], cell["row"])] = (
                cell["ref"],
                cell.get("commentAuthor", ""),
                cell["comment"],
            )
        parts.append(body)
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


def _render_rich_text(runs: list[dict]) -> str:
    """Render formatted text runs as inline HTML tags."""
    parts: list[str] = []
    for run in runs:
        txt = escape(run.get("text", ""))
        if run.get("bold"):
            txt = f"<b>{txt}</b>"
        if run.get("italic"):
            txt = f"<i>{txt}</i>"
        if run.get("underline"):
            txt = f"<u>{txt}</u>"
        if run.get("color"):
            txt = f'<color value={run["color"]}>{txt}</color>'
        parts.append(txt)
    return "".join(parts)


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
