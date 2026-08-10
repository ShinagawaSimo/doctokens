"""HTML5 renderers for XLSX workbooks — all three densities."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from .._utils import col_letter, parse_ref
from ..formats import FormatIndex
from ..models import Cell, ParsedWorkbook, RichTextRun, SheetInfo
from ._constants import (
    _CELL_BUDGET,
    _GRID_BOUND_SENTINEL,
)

Density = str  # "plain" | "structural" | "semantic"
_STYLE_RANGE_MIN_CELLS = 6


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
    return _render_grid(
        filtered,
        density,
    )


# ── Per-sheet rendering ──


def _render_sheet(
    sheet: SheetInfo,
    density: Density,
    wb: ParsedWorkbook | None = None,
    start_row: int = 1,
) -> Iterator[str]:
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

    yield from _emit_hidden_cols(sheet, density)
    yield from _emit_sheet_protection(sheet, density)
    yield from _emit_defined_names(wb, density, name)
    yield from _emit_autofilter(sheet, density)
    yield from _emit_data_validations(sheet, density)
    yield from _emit_conditional_formats(sheet, density)
    yield from _emit_external_links(wb, density)
    yield from _emit_images(sheet)
    yield from _emit_charts(sheet, density)
    yield from _emit_pivot_tables(sheet)
    yield from _emit_tables(sheet, density)

    if density == "plain":
        yield from _render_plain(
            rows,
            start_row=start_row,
            hidden_cols=sheet.get("hidden_cols", []),
        )
    else:
        yield _render_grid(
            rows,
            density,
            wb,
            start_row=start_row,
        )


def _emit_hidden_cols(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """Hidden column ranges from ``<cols>`` — emitted before ``<grid>``."""
    if density == "plain":
        return
    hidden_cols = sheet.get("hidden_cols")
    if not hidden_cols:
        return
    for cmin, cmax in hidden_cols:
        col_range = col_letter(cmin) if cmin == cmax else f"{col_letter(cmin)}:{col_letter(cmax)}"
        yield f"<columns ref={col_range} hidden>\n"


def _emit_sheet_protection(sheet: SheetInfo, density: Density) -> Iterator[str]:
    if density in {"structural", "semantic"} and sheet.get("sheet_protection"):
        yield "<sheetProtection/>\n"


def _emit_defined_names(wb: ParsedWorkbook | None, density: Density, sheet_name: str) -> Iterator[str]:
    """User-defined names scoped to this sheet or global."""
    if density not in {"structural", "semantic"} or wb is None:
        return
    defined_names = wb["metadata"].get("defined_names", [])
    for dn in defined_names:
        if dn.get("hidden"):
            continue
        scope = dn.get("scopeSheet")
        if scope and scope != sheet_name:
            continue
        if dn["name"].startswith("_xlnm."):
            continue
        name_attr = escape(dn["name"], quote=True)
        ref_attr = escape(dn["ref"], quote=True)
        yield f'<definedName name={name_attr} refersTo="{ref_attr}">\n'


def _emit_autofilter(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """AutoFilter range (all densities) and filter-column conditions (structural/semantic)."""
    filter_ref = sheet.get("filter_range")
    if not filter_ref:
        return
    yield f"<filter ref={filter_ref}>\n"
    if density in {"structural", "semantic"}:
        for fc in sheet.get("filter_cols", []):
            vals = ",".join(escape(v, quote=True) for v in fc.get("values", []))
            yield f'<condition col={fc["col"]} type={fc["type"]} values="{vals}"/>\n'


def _emit_data_validations(sheet: SheetInfo, density: Density) -> Iterator[str]:
    if density not in {"structural", "semantic"}:
        return
    for dv in sheet.get("data_validations", []):
        yield f"<dataValidation ref={dv['ranges']} type={dv['type']}/>\n"


def _emit_conditional_formats(sheet: SheetInfo, density: Density) -> Iterator[str]:
    if density not in {"structural", "semantic"}:
        return
    for cf in sheet.get("conditional_formats", []):
        yield f"<conditionalFormatting ref={cf['ranges']}>\n"
        parts = [f"<rule type={cf['ruleType']}"]
        if cf.get("formula"):
            parts.append(f' formula="{escape(cf["formula"], quote=True)}"')
        parts.append("/>\n")
        yield "".join(parts)


def _emit_external_links(wb: ParsedWorkbook | None, density: Density) -> Iterator[str]:
    if density not in {"structural", "semantic"} or wb is None:
        return
    for link in wb["metadata"].get("external_links", []):
        yield f"<externalLink target={escape(link, quote=True)}/>\n"


def _emit_images(sheet: SheetInfo) -> Iterator[str]:
    for img in sheet.get("images", []):
        yield f"<image id={img['id']} ref={img['ref']}/>\n"


def _emit_charts(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """Charts — structural shows summary attributes; semantic includes series names."""
    charts = sheet.get("charts", [])
    if density == "plain":
        if charts:
            yield f"<charts count={len(charts)}>\n"
            for ch in charts:
                names = _chart_series_names(ch)
                if names:
                    yield f'<chart names="{escape(",".join(names), quote=True)}"/>\n'
        return

    for ch in charts:
        attrs = f"id={ch['id']} ref={ch['ref']} type={ch.get('type', '?')}"
        attrs += f" series={ch.get('series_count', 0)}"
        names = _chart_series_names(ch)
        if names:
            attrs += f" names={escape(','.join(names), quote=True)}"
        if ch.get("title"):
            attrs += f" title={escape(ch['title'], quote=True)}"
        attrs += " truncated"
        yield f"<chart {attrs}/>\n"


def _chart_series_names(ch: object) -> list[str]:
    if not isinstance(ch, dict):
        return []
    ch_series = ch.get("series", [])
    if not isinstance(ch_series, list):
        return []
    names: list[str] = []
    for series in ch_series:
        if not isinstance(series, dict):
            continue
        name = series.get("name", f"S{series.get('index', '')}")
        if name:
            names.append(str(name))
    return names


def _emit_pivot_tables(sheet: SheetInfo) -> Iterator[str]:
    for pv in sheet.get("pivot_tables", []):
        yield f"<pivotTable id={pv['id']} name={escape(pv['name'], quote=True)}/>\n"


def _emit_tables(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """Table summary tags emitted before the grid."""
    if density == "plain":
        for t in sheet.get("tables", []):
            yield _plain_table_summary(t)
        return
    for t in sheet.get("tables", []):
        attrs = f"id={t['id']} name={escape(t['name'], quote=True)} ref={t['ref']}"
        if density == "semantic" and t.get("columns"):
            cols = ",".join(t["columns"])
            attrs += f' cols="{escape(cols, quote=True)}"'
        if density == "semantic" and t.get("totalsRow"):
            attrs += " totalsRow"
        yield f"<table {attrs}>\n"


def _plain_table_summary(table: object) -> str:
    """Render a human-readable table summary for plain density."""
    if not isinstance(table, dict):
        return "[Table]\n"
    name = table.get("name")
    columns = table.get("columns") or []
    if not isinstance(columns, list):
        columns = []
    column_text = ", ".join(str(col) for col in columns if col)
    if name and column_text:
        return f"[Table {name}: {column_text}]\n"
    if name:
        return f"[Table {name}]\n"
    if column_text:
        return f"[Table: {column_text}]\n"
    return "[Table]\n"


# ── Plain text ──


def _render_plain(
    rows: list[list[Cell]],
    start_row: int = 1,
    hidden_cols: list[tuple[int, int]] | None = None,
) -> Iterator[str]:
    """Tab-separated cell values, no coordinates."""
    for row_cells in rows:
        if not row_cells:
            continue
        if row_cells[0]["row"] < start_row:
            continue
        texts = [cell["text"] for cell in row_cells if not _is_hidden_col(cell["col"], hidden_cols)]
        yield "\t".join(texts) + "\n"


def _is_hidden_col(col: int, hidden_cols: list[tuple[int, int]] | None) -> bool:
    if hidden_cols is None:
        return False
    return any(start <= col <= end for start, end in hidden_cols)


# ── Grid rendering (structural / semantic) ──


def _render_grid(
    rows: list[list[Cell]],
    density: Density,
    wb: ParsedWorkbook | None = None,
    start_row: int = 1,
) -> str:
    if not rows:
        return ""

    bounds = _visible_grid_bounds(rows, start_row)
    if bounds is None:
        return ""  # start_row beyond all data rows

    min_col, min_row, max_col, max_row = bounds
    ref = f"{col_letter(min_col)}{min_row}:{col_letter(max_col)}{max_row}"
    tag = f"<grid ref={ref}"

    parts = [tag + ">\n"]
    suppressed_styles: set[str] = set()
    fmt_index = wb["fmt_index"] if wb is not None else None
    if density == "semantic" and isinstance(fmt_index, FormatIndex):
        style_ranges, suppressed_styles = _repeated_style_ranges(rows, fmt_index, start_row)
        parts.extend(style_ranges)

    comments: dict[tuple[int, int], tuple[str, str, str]] = {}  # (col,row) → (ref, author, text)
    cell_count = 0
    for row_cells in rows:
        if not row_cells:
            continue
        if row_cells[0]["row"] < start_row:
            continue
        cell_count += len(row_cells)
        parts.append(
            _render_row(
                row_cells,
                min_col,
                density,
                wb,
                comments,
                suppressed_styles,
            )
        )
        if cell_count >= _CELL_BUDGET:
            break

    parts.extend(_render_comments(comments))

    return "".join(parts)


def _visible_grid_bounds(rows: list[list[Cell]], start_row: int) -> tuple[int, int, int, int] | None:
    min_col = _GRID_BOUND_SENTINEL
    max_col = 0
    min_row = _GRID_BOUND_SENTINEL
    max_row = 0
    for row_cells in rows:
        if not row_cells or row_cells[0]["row"] < start_row:
            continue
        for cell in row_cells:
            min_col = min(min_col, cell["col"])
            max_col = max(max_col, cell["col"])
            min_row = min(min_row, cell["row"])
            max_row = max(max_row, cell["row"])
    if min_col == _GRID_BOUND_SENTINEL:
        return None
    return min_col, min_row, max_col, max_row


def _render_comments(comments: dict[tuple[int, int], tuple[str, str, str]]) -> Iterator[str]:
    for comment_id, ((_col, _row), (ref, author, text)) in enumerate(
        sorted(comments.items(), key=lambda item: (item[0][1], item[0][0]))
    ):
        attrs = f'id=comment{comment_id} cell="{escape(ref, quote=True)}"'
        if author:
            attrs += f" author={escape(author, quote=True)}"
        yield f"<comment {attrs}>{escape(text)}\n"


def _render_row(
    row_cells: list[Cell],
    grid_min_col: int,
    density: Density,
    wb: ParsedWorkbook | None = None,
    comments: dict[tuple[int, int], tuple[str, str, str]] | None = None,
    suppressed_styles: set[str] | None = None,
) -> str:
    actual_row = row_cells[0]["row"]
    parts = [_row_start_tag(row_cells[0], actual_row, density)]
    fmt_index = _workbook_format_index(wb)
    expected_col = grid_min_col
    for cell in row_cells:
        if cell.get("shadow"):
            expected_col = cell["col"] + cell.get("colspan", 1)
            continue

        parts.append(f"<{_cell_tag_attrs(cell, expected_col, density, fmt_index, suppressed_styles)}>")
        body = _cell_body(cell, density)
        if comments is not None:
            body = _body_with_comment_reference(cell, body, comments)
        parts.append(body)
        expected_col = cell["col"] + cell.get("colspan", 1)

    parts.append("\n")
    return "".join(parts)


def _row_start_tag(first_cell: Cell, row_number: int, density: Density) -> str:
    row_hidden = " hidden" if first_cell.get("hidden") else ""
    parts = [f"<tr row={row_number}{row_hidden}"]
    if density in {"structural", "semantic"} and first_cell.get("outlineLevel"):
        parts.append(f" outlineLevel={first_cell['outlineLevel']}")
        if first_cell.get("collapsed"):
            parts.append(" collapsed")
    parts.append(">")
    return "".join(parts)


def _workbook_format_index(wb: ParsedWorkbook | None) -> FormatIndex | None:
    fmt_index = wb["fmt_index"] if wb is not None else None
    return fmt_index if isinstance(fmt_index, FormatIndex) else None


def _cell_tag_attrs(
    cell: Cell,
    expected_col: int,
    density: Density,
    fmt_index: FormatIndex | None,
    suppressed_styles: set[str] | None,
) -> str:
    attrs = "td"
    if density in {"structural", "semantic"}:
        attrs += _structural_cell_attrs(cell, fmt_index)
    if density == "semantic" and fmt_index is not None and "style" in cell:
        style = fmt_index.style_attrs(cell["style"])
        if style and (suppressed_styles is None or style not in suppressed_styles):
            attrs += f" {style}"
    if cell["col"] != expected_col:
        attrs += f" col={col_letter(cell['col'])}"
    return attrs


def _structural_cell_attrs(cell: Cell, fmt_index: FormatIndex | None) -> str:
    attrs = ""
    if cell.get("colspan", 1) > 1:
        attrs += f" colspan={cell['colspan']}"
    if cell.get("rowspan", 1) > 1:
        attrs += f" rowspan={cell['rowspan']}"
    if cell.get("formula"):
        attrs += f' formula="{escape(cell["formula"], quote=True)}"'
    if cell.get("formulaType"):
        attrs += f" formulaType={escape(cell['formulaType'], quote=True)}"
    if cell.get("formulaRange"):
        attrs += f" formulaRange={escape(cell['formulaRange'], quote=True)}"
    if cell.get("spillRange"):
        attrs += f" spillRange={escape(cell['spillRange'], quote=True)}"
    if cell.get("spillFrom"):
        attrs += f' spillFrom="{escape(cell["spillFrom"], quote=True)}"'
    if fmt_index is not None and "style" in cell:
        protection = fmt_index.protection_attrs(cell["style"])
        if protection:
            attrs += f" {protection}"
    return attrs


def _cell_body(cell: Cell, density: Density) -> str:
    body = _render_rich_text(cell["rich"]) if density == "semantic" and cell.get("rich") else escape(cell["text"])
    if cell.get("hyperlink"):
        return f'<a href="{escape(cell["hyperlink"], quote=True)}">{body}</a>'
    return body


def _body_with_comment_reference(
    cell: Cell,
    body: str,
    comments: dict[tuple[int, int], tuple[str, str, str]],
) -> str:
    if not cell.get("comment"):
        return body
    comment_id = len(comments)
    comments[(cell["col"], cell["row"])] = (
        cell["ref"],
        cell.get("commentAuthor", ""),
        cell["comment"],
    )
    return f"{body}<commentref id=comment{comment_id}/>"


def _repeated_style_ranges(
    rows: list[list[Cell]],
    fmt_index: FormatIndex,
    start_row: int,
) -> tuple[list[str], set[str]]:
    cells_by_style: dict[str, set[tuple[int, int]]] = {}
    for row_cells in rows:
        if not row_cells or row_cells[0]["row"] < start_row:
            continue
        for cell in row_cells:
            if cell.get("shadow") or "style" not in cell:
                continue
            style = fmt_index.style_attrs(cell["style"])
            if not _is_groupable_style(style):
                continue
            cells = cells_by_style.setdefault(style, set())
            for row in range(cell["row"], cell["row"] + cell.get("rowspan", 1)):
                for col in range(cell["col"], cell["col"] + cell.get("colspan", 1)):
                    cells.add((row, col))

    suppressed_styles = {style for style, cells in cells_by_style.items() if len(cells) >= _STYLE_RANGE_MIN_CELLS}
    lines: list[str] = []
    for style in sorted(suppressed_styles):
        for start_col, first_row, end_col, last_row in _rectangular_ranges(cells_by_style[style]):
            ref = _range_ref(start_col, first_row, end_col, last_row)
            lines.append(f'<styleRange ref={ref} attrs="{escape(style, quote=True)}"/>\n')
    return lines, suppressed_styles


def _is_groupable_style(style: str) -> bool:
    return "color=" in style or "fill=" in style


def _rectangular_ranges(cells: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    spans_by_row: dict[int, list[tuple[int, int]]] = {}
    for row in sorted({row for row, _col in cells}):
        cols = sorted(col for item_row, col in cells if item_row == row)
        spans_by_row[row] = _horizontal_spans(cols)

    finished: list[tuple[int, int, int, int]] = []
    active: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for row in sorted(spans_by_row):
        current: set[tuple[int, int]] = set()
        for start_col, end_col in spans_by_row[row]:
            key = (start_col, end_col)
            current.add(key)
            existing = active.get(key)
            if existing is not None and existing[3] == row - 1:
                active[key] = (existing[0], existing[1], existing[2], row)
            else:
                if existing is not None:
                    finished.append(existing)
                active[key] = (start_col, row, end_col, row)
        expired = [key for key in active if key not in current and active[key][3] < row]
        finished.extend(active.pop(key) for key in expired)
    finished.extend(active.values())
    return sorted(finished, key=lambda item: (item[1], item[0], item[3], item[2]))


def _horizontal_spans(cols: list[int]) -> list[tuple[int, int]]:
    if not cols:
        return []
    spans: list[tuple[int, int]] = []
    start = prev = cols[0]
    for col in cols[1:]:
        if col == prev + 1:
            prev = col
            continue
        spans.append((start, prev))
        start = prev = col
    spans.append((start, prev))
    return spans


def _range_ref(start_col: int, start_row: int, end_col: int, end_row: int) -> str:
    start = f"{col_letter(start_col)}{start_row}"
    end = f"{col_letter(end_col)}{end_row}"
    return start if start == end else f"{start}:{end}"


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
    sc, sr = parse_ref(start_ref)
    ec, er = parse_ref(end_ref)
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
        kept = [c for c in row_cells if start_col <= c["col"] <= end_col and start_row <= c["row"] <= end_row]
        if kept:
            result.append(kept)
    return result


def _render_rich_text(runs: list[RichTextRun]) -> str:
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
            txt = f"<color value={run['color']}>{txt}</color>"
        parts.append(txt)
    return "".join(parts)
