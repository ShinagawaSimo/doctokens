"""Output renderers for XLSX workbooks at all three densities."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from html import escape as escape_text

from .._utils import col_letter, parse_ref
from ..formats import FormatIndex
from ..models import Cell, ParsedWorkbook, RichTextRun, SheetInfo, ThreadedComment
from ._constants import (
    _CELL_BUDGET,
    _GRID_BOUND_SENTINEL,
)

Density = str  # "plain" | "structural" | "semantic"
_STYLE_RANGE_MIN_CELLS = 6


@dataclass(frozen=True)
class _CommentRecord:
    id: str
    ref: str
    text: str
    author: str = ""
    date: str = ""
    parent_id: str = ""
    resolved: bool = False
    mentions: tuple[str, ...] = ()


@dataclass
class _CommentCollector:
    """Assign compact display IDs while retaining per-cell threaded conversations."""

    by_cell: dict[tuple[int, int], list[_CommentRecord]] = field(default_factory=dict)
    _legacy_index: int = 0

    def register(self, cell: Cell) -> tuple[_CommentRecord, ...]:
        key = (cell["col"], cell["row"])
        existing = self.by_cell.get(key)
        if existing is not None:
            return tuple(existing)
        records: list[_CommentRecord] = []
        if cell.get("comment") is not None:
            records.append(
                _CommentRecord(
                    id=f"comment{self._legacy_index}",
                    ref=cell["ref"],
                    text=cell["comment"],
                    author=cell.get("commentAuthor", ""),
                )
            )
            self._legacy_index += 1
        records.extend(_threaded_comment_record(cell["ref"], item) for item in cell.get("threadedComments", []))
        if records:
            self.by_cell[key] = records
        return tuple(records)


# ── Public API ──


def render_workbook(parsed_workbook: ParsedWorkbook, *, density: Density = "structural") -> str:
    """Render a parsed workbook at the requested output density."""
    return "".join(iter_workbook(parsed_workbook, density=density))


def iter_workbook(parsed_workbook: ParsedWorkbook, *, density: Density = "structural") -> Iterator[str]:
    """Yield workbook output chunks whose concatenation matches render_workbook."""
    yield f"density={density}\n"
    for sheet_index, worksheet_info in enumerate(parsed_workbook["sheets"]):
        yield from _render_sheet(
            worksheet_info,
            density,
            parsed_workbook,
            emit_globals=sheet_index == 0,
        )


def render_range(
    parsed_workbook: ParsedWorkbook,
    sheet: str,
    range_spec: str,
    *,
    density: Density = "structural",
) -> str:
    """Render cells within an A1-style range, e.g. ``"A1:H30"``.

    Returns the ``<grid ref=...>`` block for the matching sheet.
    Raises ``ValueError`` if the sheet is not found or the range is invalid.
    """
    worksheet_info = _find_sheet(parsed_workbook, sheet)
    start_col, start_row, end_col, end_row = _parse_range(range_spec)

    worksheet_rows = worksheet_info.get("rows", [])
    selected_rows = _filter_rows(worksheet_rows, start_col, start_row, end_col, end_row)
    return _render_grid(
        selected_rows,
        density,
    )


# ── Per-sheet rendering ──


def _render_sheet(
    worksheet_info: SheetInfo,
    density: Density,
    parsed_workbook: ParsedWorkbook | None = None,
    start_row: int = 1,
    emit_globals: bool = True,
) -> Iterator[str]:
    worksheet_name = worksheet_info["name"]
    visibility_state = worksheet_info.get("state", "visible")
    worksheet_kind = worksheet_info.get("kind", "worksheet")

    if worksheet_kind == "chartsheet":
        yield f"<chartsheet name={escape_text(worksheet_name, quote=True)}>\n"
        return

    attrs = f"name={escape_text(worksheet_name, quote=True)}"
    if visibility_state == "hidden":
        attrs += " hidden"
    elif visibility_state == "veryHidden":
        attrs += " veryHidden"
    yield f"<sheet {attrs}>\n"

    worksheet_rows = worksheet_info.get("rows", [])

    yield from _emit_hidden_cols(worksheet_info, density)
    yield from _emit_sheet_protection(worksheet_info, density)
    yield from _emit_defined_names(parsed_workbook, density, worksheet_name, emit_globals=emit_globals)
    yield from _emit_autofilter(worksheet_info, density)
    yield from _emit_data_validations(worksheet_info, density)
    yield from _emit_conditional_formats(worksheet_info, density)
    yield from _emit_external_links(parsed_workbook, density)
    yield from _emit_pivot_context(parsed_workbook, density, emit=emit_globals)
    yield from _emit_images(worksheet_info, density)
    yield from _emit_charts(worksheet_info, density)
    yield from _emit_pivot_tables(worksheet_info, density)
    yield from _emit_tables(worksheet_info, density)

    if density == "plain":
        yield from _render_plain(
            worksheet_rows,
            start_row=start_row,
            hidden_cols=worksheet_info.get("hidden_cols", []),
        )
    else:
        yield _render_grid(
            worksheet_rows,
            density,
            parsed_workbook,
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


def _emit_defined_names(
    parsed_workbook: ParsedWorkbook | None,
    density: Density,
    sheet_name: str,
    *,
    emit_globals: bool = True,
) -> Iterator[str]:
    """User-defined names scoped to this sheet or global.

    Global names are emitted once, with the first sheet's block, instead of
    repeating the same declaration on every sheet.
    """
    if density not in {"structural", "semantic"} or parsed_workbook is None:
        return
    defined_names = parsed_workbook["metadata"].get("defined_names", [])
    for defined_name in defined_names:
        if defined_name.get("hidden"):
            continue
        scope = defined_name.get("scopeSheet")
        if scope and scope != sheet_name:
            continue
        if scope is None and not emit_globals:
            continue
        if defined_name["name"].startswith("_xlnm."):
            continue
        name_attr = escape_text(defined_name["name"], quote=True)
        ref_attr = escape_text(defined_name["ref"], quote=True)
        yield f'<definedName name={name_attr} refersTo="{ref_attr}">\n'


def _emit_autofilter(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """AutoFilter range (all densities) and filter-column conditions (structural/semantic)."""
    filter_ref = sheet.get("filter_range")
    if not filter_ref:
        return
    if density == "plain":
        yield f"[Filter {filter_ref}]\n"
        return
    yield f"<filter ref={filter_ref}>\n"
    for fc in sheet.get("filter_cols", []):
        attrs = [f"col={fc['col']}", f"type={fc['type']}"]
        if values := fc.get("values"):
            attrs.append(f'values="{escape_text(",".join(values), quote=True)}"')
        if fc.get("blank"):
            attrs.append("blank")
        attrs.extend(
            f'{key}="{escape_text(str(value), quote=True)}"'
            for key in ("calendarType", "operator", "value", "value2", "rank", "filterValue", "iconSet")
            if (value := fc.get(key))
        )
        attrs.extend(key for key in ("and", "top", "percent") if fc.get(key))
        if "cellColor" in fc:
            attrs.append(f"cellColor={int(bool(fc['cellColor']))}")
        attrs.extend(f"{key}={value}" for key in ("dxfId", "iconId") if (value := fc.get(key)) is not None)
        if date_groups := fc.get("dateGroup"):
            groups = ";".join(":".join(f"{key}={value}" for key, value in sorted(group.items())) for group in date_groups)
            attrs.append(f'groups="{escape_text(groups, quote=True)}"')
        yield f"<condition {' '.join(attrs)}/>\n"


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
        parts = [f"<rule type={cf['ruleType']} priority={cf.get('priority', 0)}"]
        formulas = cf.get("formulas") or []
        if len(formulas) == 1:
            parts.append(f' formula="{escape_text(formulas[0], quote=True)}"')
        elif formulas:
            parts.append(f' formulas="{escape_text(" | ".join(formulas), quote=True)}"')
        if cf.get("operator"):
            parts.append(f' operator="{escape_text(cf["operator"], quote=True)}"')
        if cf.get("text"):
            parts.append(f' text="{escape_text(cf["text"], quote=True)}"')
        if cf.get("dxfId") is not None:
            parts.append(f" dxf={cf['dxfId']}")
        if cf.get("dxfStyle"):
            parts.append(f' style="{escape_text(cf["dxfStyle"], quote=True)}"')
        if cf.get("stopIfTrue"):
            parts.append(" stopIfTrue")
        if cf.get("rank") is not None:
            parts.append(f" rank={cf['rank']}")
        if cf.get("percent"):
            parts.append(" percent")
        if cf.get("formatKind"):
            parts.append(f" format={cf['formatKind']}")
            if density == "semantic":
                details = _format_conditional_details(cf.get("formatDetails"))
                if details:
                    parts.append(f' details="{escape_text(details, quote=True)}"')
        parts.append("/>\n")
        yield "".join(parts)


def _format_conditional_details(details: object) -> str:
    if not isinstance(details, dict):
        return ""

    values: list[str] = []
    for key, value in details.items():
        if key == "stops" and isinstance(value, list):
            stops = [
                ":".join(f"{item_key}={item_value}" for item_key, item_value in item.items())
                for item in value
                if isinstance(item, dict)
            ]
            if stops:
                values.append(f"stops={';'.join(stops)}")
            continue
        if key == "thresholds" and isinstance(value, list):
            thresholds = [
                ":".join(f"{item_key}={item_value}" for item_key, item_value in item.items())
                for item in value
                if isinstance(item, dict)
            ]
            if thresholds:
                values.append(f"thresholds={';'.join(thresholds)}")
            continue
        values.append(f"{key}={value}")
    return ";".join(values)


def _emit_external_links(parsed_workbook: ParsedWorkbook | None, density: Density) -> Iterator[str]:
    if density not in {"structural", "semantic"} or parsed_workbook is None:
        return
    for link in parsed_workbook["metadata"].get("external_links", []):
        yield f"<externalLink target={escape_text(link, quote=True)}/>\n"


def _emit_pivot_context(
    parsed_workbook: ParsedWorkbook | None,
    density: Density,
    *,
    emit: bool,
) -> Iterator[str]:
    """Emit workbook-level pivot sources and interactive filters once."""
    if parsed_workbook is None or not emit:
        return
    metadata = parsed_workbook["metadata"]
    if density == "plain":
        for slicer in metadata.get("slicers", []):
            name = slicer.get("name") or slicer.get("sourceName")
            yield f"[Slicer {name}]\n" if name else "[Slicer]\n"
        for timeline in metadata.get("timelines", []):
            name = timeline.get("name") or timeline.get("sourceName")
            yield f"[Timeline {name}]\n" if name else "[Timeline]\n"
        return
    for cache in metadata.get("pivot_caches", []):
        attrs = [f"id={cache['id']}", f"cacheId={cache['cacheId']}"]
        if cache.get("sourceSheet"):
            attrs.append(f'sheet="{escape_text(cache["sourceSheet"], quote=True)}"')
        if cache.get("sourceRef"):
            attrs.append(f"ref={cache['sourceRef']}")
        if cache.get("refreshOnLoad"):
            attrs.append("refreshOnLoad")
        if density == "semantic" and cache.get("fields"):
            attrs.append(f'fields="{escape_text(",".join(cache["fields"]), quote=True)}"')
        yield f"<pivotCache {' '.join(attrs)}/>\n"
    for slicer in metadata.get("slicers", []):
        attrs = [f"id={slicer['id']}", "type=slicer"]
        if slicer.get("name"):
            attrs.append(f'name="{escape_text(slicer["name"], quote=True)}"')
        if slicer.get("sourceName"):
            attrs.append(f'source="{escape_text(slicer["sourceName"], quote=True)}"')
        if slicer.get("cacheId") is not None:
            attrs.append(f"cacheId={slicer['cacheId']}")
        yield f"<slicer {' '.join(attrs)}/>\n"
    for timeline in metadata.get("timelines", []):
        attrs = [f"id={timeline['id']}"]
        if timeline.get("name"):
            attrs.append(f'name="{escape_text(timeline["name"], quote=True)}"')
        if timeline.get("sourceName"):
            attrs.append(f'source="{escape_text(timeline["sourceName"], quote=True)}"')
        if timeline.get("level"):
            attrs.append(f"level={timeline['level']}")
        yield f"<timeline {' '.join(attrs)}/>\n"


def _emit_images(sheet: SheetInfo, density: Density) -> Iterator[str]:
    if density == "plain":
        for img in sheet.get("images", []):
            yield f"[Image {img['id']} at {img['ref']}]\n"
        return
    for img in sheet.get("images", []):
        yield f"<image id={img['id']} ref={img['ref']}/>\n"


def _emit_charts(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """Charts — structural shows summary attributes; semantic includes series names."""
    charts = sheet.get("charts", [])
    if density == "plain":
        for ch in charts:
            title_part = f" {ch.get('title')}" if ch.get("title") else ""
            names_text = ", ".join(_chart_series_names(ch))
            names_part = f": {names_text}" if names_text else ""
            yield f"[Chart{title_part}{names_part}]\n"
        return

    for ch in charts:
        attrs = f"id={ch['id']} ref={ch['ref']} type={ch.get('type', '?')}"
        if ch.get("plotTypes"):
            attrs += f" plots={escape_text(','.join(ch['plotTypes']), quote=True)}"
        attrs += f" series={ch.get('series_count', 0)}"
        names = _chart_series_names(ch)
        if names:
            attrs += f" names={escape_text(','.join(names), quote=True)}"
        if ch.get("title"):
            attrs += f" title={escape_text(ch['title'], quote=True)}"
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


def _emit_pivot_tables(sheet: SheetInfo, density: Density) -> Iterator[str]:
    if density == "plain":
        for pv in sheet.get("pivot_tables", []):
            name_part = f" {pv['name']}" if pv.get("name") else ""
            yield f"[PivotTable{name_part}]\n"
        return
    for pv in sheet.get("pivot_tables", []):
        attrs = [f"id={pv['id']}", f"name={escape_text(pv.get('name', ''), quote=True)}"]
        if pv.get("ref"):
            attrs.append(f"ref={pv['ref']}")
        if pv.get("sourceSheet"):
            attrs.append(f'sourceSheet="{escape_text(pv["sourceSheet"], quote=True)}"')
        if pv.get("sourceRef"):
            attrs.append(f"sourceRef={pv['sourceRef']}")
        if density == "semantic" and pv.get("rowFields"):
            attrs.append(f'rows="{escape_text(",".join(pv["rowFields"]), quote=True)}"')
        if density == "semantic" and pv.get("columnFields"):
            attrs.append(f'columns="{escape_text(",".join(pv["columnFields"]), quote=True)}"')
        if density == "semantic" and pv.get("pageFields"):
            attrs.append(f'pages="{escape_text(",".join(pv["pageFields"]), quote=True)}"')
        if density == "semantic" and pv.get("dataFields"):
            attrs.append(f'values="{escape_text(",".join(pv["dataFields"]), quote=True)}"')
        if density == "semantic" and pv.get("filters"):
            attrs.append(f'filters="{escape_text(",".join(pv["filters"]), quote=True)}"')
        yield f"<pivotTable {' '.join(attrs)}/>\n"


def _emit_tables(sheet: SheetInfo, density: Density) -> Iterator[str]:
    """Table summary tags emitted before the grid."""
    if density == "plain":
        for t in sheet.get("tables", []):
            yield _plain_table_summary(t)
        return
    for t in sheet.get("tables", []):
        attrs = f"id={t['id']} name={escape_text(t['name'], quote=True)} ref={t['ref']}"
        if density == "semantic" and t.get("columns"):
            cols = ",".join(t["columns"])
            attrs += f' cols="{escape_text(cols, quote=True)}"'
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
        texts = [
            f"{_plain_cell_text(cell)}{_plain_comment_suffix(cell)}"
            for cell in row_cells
            if not _is_hidden_col(cell["col"], hidden_cols)
        ]
        yield "\t".join(texts) + "\n"


def _is_hidden_col(col: int, hidden_cols: list[tuple[int, int]] | None) -> bool:
    if hidden_cols is None:
        return False
    return any(start <= col <= end for start, end in hidden_cols)


def _plain_comment_suffix(cell: Cell) -> str:
    """Keep review context in plain output without rendering implementation IDs."""
    parts: list[str] = []
    if cell.get("comment") is not None:
        author = cell.get("commentAuthor", "")
        prefix = f" by {author}" if author else ""
        parts.append(f"[Comment{prefix}: {cell['comment']}]")
    for item in cell.get("threadedComments", []):
        author = item.get("author", "")
        qualifiers: list[str] = [author] if author else []
        if item.get("parentId"):
            qualifiers.append("reply")
        if item.get("resolved"):
            qualifiers.append("resolved")
        label = f" ({', '.join(qualifiers)})" if qualifiers else ""
        parts.append(f"[Comment{label}: {item.get('text', '')}]")
    return " " + " ".join(parts) if parts else ""


def _plain_cell_text(cell: Cell) -> str:
    if (control := cell.get("cellControl")) and control.get("kind") == "checkbox":
        return f"[Checkbox {control.get('state', cell['text'])}]"
    if rich_value := cell.get("richValue"):
        if rich_value.get("imagePart") or rich_value.get("imageUrl"):
            return rich_value.get("alt") or rich_value.get("display") or "[Image]"
        return rich_value.get("display") or rich_value.get("fallback") or cell["text"]
    return cell["text"]


# ── Grid rendering (structural / semantic) ──


def _render_grid(
    rows: list[list[Cell]],
    density: Density,
    parsed_workbook: ParsedWorkbook | None = None,
    start_row: int = 1,
    cell_budget: int | None = _CELL_BUDGET,
) -> str:
    """Render the cell grid.

    The default view is capped at *cell_budget* cells; when rows remain
    beyond the cap, the grid carries a ``truncated`` marker so consumers
    know to page via render_range.  *cell_budget=None* disables truncation
    (exact reads).
    """
    if not rows:
        return ""

    bounds = _visible_grid_bounds(rows, start_row)
    if bounds is None:
        return ""  # start_row beyond all data rows

    min_col, min_row, max_col, max_row = bounds
    visible_rows = [row_cells for row_cells in rows if row_cells and row_cells[0]["row"] >= start_row]

    suppressed_styles: set[str] = set()
    format_index = parsed_workbook["fmt_index"] if parsed_workbook is not None else None
    style_parts: list[str] = []
    if density == "semantic" and isinstance(format_index, FormatIndex):
        style_ranges, suppressed_styles = _repeated_style_ranges(rows, format_index, start_row)
        style_parts.extend(style_ranges)

    comments = _CommentCollector()
    cell_count = 0
    truncated = False
    body_parts: list[str] = []
    for index, row_cells in enumerate(visible_rows):
        cell_count += len(row_cells)
        body_parts.append(
            _render_row(
                row_cells,
                min_col,
                density,
                parsed_workbook,
                comments,
                suppressed_styles,
            )
        )
        if cell_budget is not None and cell_count >= cell_budget:
            truncated = index + 1 < len(visible_rows)
            break

    ref = f"{col_letter(min_col)}{min_row}:{col_letter(max_col)}{max_row}"
    tag = f"<grid ref={ref}"
    if truncated:
        tag += " truncated"
    output_parts = [tag + ">\n", *style_parts, *body_parts]
    output_parts.extend(_render_comments(comments))

    return "".join(output_parts)


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


def _render_comments(comments: _CommentCollector) -> Iterator[str]:
    for _coord, records in sorted(comments.by_cell.items(), key=lambda item: (item[0][1], item[0][0])):
        for comment in records:
            attrs = f'id={escape_text(comment.id, quote=True)} cell="{escape_text(comment.ref, quote=True)}"'
            if comment.author:
                attrs += f" author={escape_text(comment.author, quote=True)}"
            if comment.date:
                attrs += f" date={escape_text(comment.date, quote=True)}"
            if comment.parent_id:
                attrs += f" parent={escape_text(comment.parent_id, quote=True)}"
            if comment.resolved:
                attrs += " resolved"
            if comment.mentions:
                attrs += f' mentions="{escape_text(", ".join(comment.mentions), quote=True)}"'
            yield f"<comment {attrs}>{escape_text(comment.text)}\n"


def _render_row(
    row_cells: list[Cell],
    grid_min_col: int,
    density: Density,
    parsed_workbook: ParsedWorkbook | None = None,
    comments: _CommentCollector | None = None,
    suppressed_styles: set[str] | None = None,
) -> str:
    actual_row = row_cells[0]["row"]
    output_parts = [_row_start_tag(row_cells[0], actual_row, density)]
    format_index = _workbook_format_index(parsed_workbook)
    expected_col = grid_min_col
    for cell in row_cells:
        if cell.get("shadow"):
            expected_col = cell["col"] + cell.get("colspan", 1)
            continue

        output_parts.append(f"<{_cell_tag_attrs(cell, expected_col, density, format_index, suppressed_styles)}>")
        body = _cell_body(cell, density)
        if comments is not None:
            body = _body_with_comment_reference(cell, body, comments)
        output_parts.append(body)
        expected_col = cell["col"] + cell.get("colspan", 1)

    output_parts.append("\n")
    return "".join(output_parts)


def _row_start_tag(first_cell: Cell, row_number: int, density: Density) -> str:
    row_hidden = " hidden" if first_cell.get("hidden") else ""
    output_parts = [f"<tr row={row_number}{row_hidden}"]
    if density in {"structural", "semantic"} and first_cell.get("outlineLevel"):
        output_parts.append(f" outlineLevel={first_cell['outlineLevel']}")
        if first_cell.get("collapsed"):
            output_parts.append(" collapsed")
    output_parts.append(">")
    return "".join(output_parts)


def _workbook_format_index(parsed_workbook: ParsedWorkbook | None) -> FormatIndex | None:
    format_index = parsed_workbook["fmt_index"] if parsed_workbook is not None else None
    return format_index if isinstance(format_index, FormatIndex) else None


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


def _structural_cell_attrs(cell: Cell, format_index: FormatIndex | None) -> str:
    attrs = ""
    if cell.get("colspan", 1) > 1:
        attrs += f" colspan={cell['colspan']}"
    if cell.get("rowspan", 1) > 1:
        attrs += f" rowspan={cell['rowspan']}"
    if cell.get("formula"):
        attrs += f' formula="{escape_text(cell["formula"], quote=True)}"'
    if cell.get("formulaType"):
        attrs += f" formulaType={escape_text(cell['formulaType'], quote=True)}"
    if cell.get("formulaRange"):
        attrs += f" formulaRange={escape_text(cell['formulaRange'], quote=True)}"
    if cell.get("spillRange"):
        attrs += f" spillRange={escape_text(cell['spillRange'], quote=True)}"
    if cell.get("spillFrom"):
        attrs += f' spillFrom="{escape_text(cell["spillFrom"], quote=True)}"'
    if format_index is not None and "style" in cell:
        protection = format_index.protection_attrs(cell["style"])
        if protection:
            attrs += f" {protection}"
    if control := cell.get("cellControl"):
        attrs += f" control={control.get('kind', 'unknown')}"
        if control.get("state"):
            attrs += f" state={control['state']}"
        if control.get("default") is not None:
            attrs += f" default={control['default']}"
    if rich_value := cell.get("richValue"):
        attrs += f' richType="{escape_text(rich_value.get("type", "rich"), quote=True)}"'
        if rich_value.get("imagePart") or rich_value.get("imageUrl"):
            attrs += " inCellImage"
            if rich_value.get("alt"):
                attrs += f' alt="{escape_text(rich_value["alt"], quote=True)}"'
    return attrs


def _cell_body(cell: Cell, density: Density) -> str:
    rich_value = cell.get("richValue")
    if rich_value and (density == "plain" or rich_value.get("display") or rich_value.get("fallback")):
        if rich_value.get("imagePart") or rich_value.get("imageUrl"):
            output_body = escape_text(rich_value.get("alt") or rich_value.get("display") or "[Image]")
        else:
            output_body = escape_text(rich_value.get("display") or rich_value.get("fallback") or cell["text"])
    else:
        output_body = _render_rich_text(cell["rich"]) if density == "semantic" and cell.get("rich") else escape_text(cell["text"])
    if density == "semantic" and rich_value and rich_value.get("fields"):
        visible_fields = "; ".join(
            f"{key}={value}"
            for key, value in rich_value["fields"].items()
            if not key.startswith("_") and key not in {"CalcOrigin", "ImageSizing", "ImageWidth", "ImageHeight"}
        )
        if visible_fields:
            output_body += f' <richValue fields="{escape_text(visible_fields, quote=True)}"/>'
    if cell.get("hyperlink"):
        return f'<a href="{escape_text(cell["hyperlink"], quote=True)}">{output_body}</a>'
    return output_body


def _body_with_comment_reference(
    cell: Cell,
    body: str,
    comments: _CommentCollector,
) -> str:
    records = comments.register(cell)
    if not records:
        return body
    if len(records) == 1:
        return f"{body}<commentref id={records[0].id}/>"
    ids = " ".join(record.id for record in records)
    return f'<commentref ids="{escape_text(ids, quote=True)}"/>'


def _threaded_comment_record(ref: str, item: ThreadedComment) -> _CommentRecord:
    mentions = tuple(
        mention["person"] for mention in item.get("mentions", []) if isinstance(mention.get("person"), str) and mention["person"]
    )
    return _CommentRecord(
        id=item.get("id", ""),
        ref=ref,
        text=item.get("text", ""),
        author=item.get("author", ""),
        date=item.get("date", ""),
        parent_id=item.get("parentId", ""),
        resolved=bool(item.get("resolved")),
        mentions=mentions,
    )


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
        lines.append(f'<styleRange ref={ref} attrs="{escape_text(style, quote=True)}"/>\n')
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


def _find_sheet(parsed_workbook: ParsedWorkbook, worksheet_name: str) -> SheetInfo:
    for worksheet_info in parsed_workbook["sheets"]:
        if worksheet_info["name"] == worksheet_name:
            return worksheet_info
    raise ValueError(f"Sheet {worksheet_name!r} not found")


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
    selected_rows: list[list[Cell]] = []
    for row_cells in rows:
        kept_cells = [cell for cell in row_cells if start_col <= cell["col"] <= end_col and start_row <= cell["row"] <= end_row]
        if kept_cells:
            selected_rows.append(kept_cells)
    return selected_rows


def _render_rich_text(runs: list[RichTextRun]) -> str:
    """Render formatted text runs as inline output tags."""
    output_parts: list[str] = []
    for text_run in runs:
        run_output = escape_text(text_run.get("text", ""))
        if text_run.get("bold"):
            run_output = f"<b>{run_output}</b>"
        if text_run.get("italic"):
            run_output = f"<i>{run_output}</i>"
        if text_run.get("underline"):
            run_output = f"<u>{run_output}</u>"
        if text_run.get("color"):
            run_output = f"<color value={text_run['color']}>{run_output}</color>"
        output_parts.append(run_output)
    return "".join(output_parts)
