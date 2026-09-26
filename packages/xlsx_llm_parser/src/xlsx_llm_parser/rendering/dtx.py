"""Direct DTX serialization for XLSX parsed workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append, element, serialize, text

from .._utils import col_letter
from ..models import Cell, ParsedWorkbook, SheetInfo, WorkbookMetadata
from ..parsing.modules.styles.index import FormatIndex
from ._constants import _CELL_BUDGET, _GRID_BOUND_SENTINEL

_STYLE_RANGE_MIN_CELLS = 6


def iter_dtx(parsed_workbook: ParsedWorkbook, density: str) -> Iterator[str]:
    """Yield one DTX workbook directly from parsed worksheet IR."""
    root = element("workbook", density=density, format="xlsx", schema="doctokens-xml", version="1.0")
    _append_workbook_metadata(root, parsed_workbook, density)
    for sheet_index, sheet in enumerate(parsed_workbook["sheets"]):
        _append_sheet(root, sheet, parsed_workbook, density, emit_globals=sheet_index == 0)
    yield serialize(root)


def render_sheet_dtx(
    parsed_workbook: ParsedWorkbook,
    sheet: SheetInfo,
    density: str,
    rows: list[list[Cell]] | None = None,
) -> str:
    """Render a selected sheet or range as an independent DTX workbook."""
    root = element("workbook", density=density, format="xlsx", schema="doctokens-xml", version="1.0")
    selected = cast(SheetInfo, dict(sheet))
    if rows is not None:
        selected["rows"] = rows
    _append_sheet(root, selected, parsed_workbook, density, emit_globals=True, cell_budget=None)
    return serialize(root)


def _append_workbook_metadata(parent: ET.Element, workbook: ParsedWorkbook, density: str) -> None:
    metadata = workbook["metadata"]
    if density not in {"structural", "semantic"}:
        return
    defined = [item for item in metadata.get("defined_names", []) if not item.get("hidden") and item.get("scopeSheet") is None]
    if defined:
        group = append(parent, "defined-names")
        for item in defined:
            append(group, "defined-name", item["ref"], name=item["name"])
    external_links = metadata.get("external_links", [])
    if external_links:
        group = append(parent, "external-links")
        for target in external_links:
            append(group, "external-link", target=target)
    _append_pivot_context(parent, metadata, density)


def _append_sheet(
    parent: ET.Element,
    sheet: SheetInfo,
    workbook: ParsedWorkbook,
    density: str,
    *,
    emit_globals: bool,
    cell_budget: int | None = _CELL_BUDGET,
) -> None:
    if sheet.get("kind") == "chartsheet":
        append(parent, "chart-sheet", name=sheet["name"])
        return
    visibility = sheet.get("state", "visible")
    node = append(parent, "sheet", name=sheet["name"], visibility=visibility if visibility != "visible" else None)
    _append_sheet_metadata(node, sheet, workbook, density, emit_globals)
    if density in {"structural", "semantic"}:
        _append_grid(node, sheet.get("rows", []), workbook, density, cell_budget=cell_budget)


def _append_sheet_metadata(
    parent: ET.Element,
    sheet: SheetInfo,
    workbook: ParsedWorkbook,
    density: str,
    emit_globals: bool,
) -> None:
    if density not in {"structural", "semantic"}:
        return
    for first, last in sheet.get("hidden_cols", []):
        ref = col_letter(first) if first == last else f"{col_letter(first)}:{col_letter(last)}"
        append(parent, "columns", ref=ref, hidden=True)
    if sheet.get("sheet_protection"):
        append(parent, "sheet-protection")
    for defined_name in workbook["metadata"].get("defined_names", []):
        if defined_name.get("hidden") or defined_name["name"].startswith("_xlnm."):
            continue
        scope = defined_name.get("scopeSheet")
        if scope == sheet["name"]:
            append(parent, "defined-name", defined_name["ref"], name=defined_name["name"])
        elif scope is None and emit_globals:
            # Global definitions live once at root and are not duplicated here.
            continue
    if sheet.get("filter_range"):
        filter_node = append(parent, "filter", ref=sheet["filter_range"])
        for condition in sheet.get("filter_cols", []):
            attrs: dict[str, object] = {"column": condition.get("col"), "type": condition.get("type")}
            for old, new in (
                ("values", "values"),
                ("calendarType", "calendar_type"),
                ("operator", "operator"),
                ("value", "value"),
                ("value2", "value2"),
                ("rank", "rank"),
                ("filterValue", "filter_value"),
                ("iconSet", "icon_set"),
                ("dxfId", "dxf_id"),
                ("iconId", "icon_id"),
            ):
                value = condition.get(old)
                if value not in (None, "", []):
                    attrs[new] = ",".join(value) if old == "values" and isinstance(value, list) else value
            for old, new in (
                ("blank", "blank"),
                ("and", "and"),
                ("top", "top"),
                ("percent", "percent"),
                ("cellColor", "cell_color"),
            ):
                if condition.get(old):
                    attrs[new] = True
            if "cellColor" in condition:
                attrs["cell_color"] = bool(condition["cellColor"])
            if date_groups := condition.get("dateGroup"):
                attrs["groups"] = ";".join(
                    ":".join(f"{key}={value}" for key, value in sorted(group.items())) for group in date_groups
                )
            append(filter_node, "condition", **attrs)
    for validation in sheet.get("data_validations", []):
        append(parent, "data-validation", ref=validation.get("ranges"), type=validation.get("type"))
    _append_conditional_formats(parent, sheet, density)
    for image in sheet.get("images", []):
        append(parent, "img", id=image.get("id"), ref=image.get("ref"))
    for chart in sheet.get("charts", []):
        append(
            parent,
            "chart",
            id=chart.get("id"),
            ref=chart.get("ref"),
            type=chart.get("type", "?"),
            plots=",".join(chart.get("plotTypes", [])) or None,
            series=chart.get("series_count", 0),
            names=",".join(_chart_names(chart)) or None,
            title=chart.get("title"),
            truncated=True,
        )
    for pivot in sheet.get("pivot_tables", []):
        pivot_attrs: dict[str, object] = {
            "id": pivot.get("id"),
            "name": pivot.get("name"),
            "ref": pivot.get("ref"),
            "source_sheet": pivot.get("sourceSheet"),
            "source_ref": pivot.get("sourceRef"),
        }
        if density == "semantic":
            for old, new in (
                ("rowFields", "rows"),
                ("columnFields", "columns"),
                ("pageFields", "pages"),
                ("dataFields", "values"),
                ("filters", "filters"),
            ):
                values = pivot.get(old)
                if values:
                    pivot_attrs[new] = _joined(values)
        append(parent, "pivot-table", **pivot_attrs)
    for table in sheet.get("tables", []):
        append(
            parent,
            "table-summary",
            id=table.get("id"),
            name=table.get("name"),
            ref=table.get("ref"),
            columns=",".join(table.get("columns", [])) if density == "semantic" else None,
            totals_row=True if density == "semantic" and table.get("totalsRow") else None,
        )


def _append_conditional_formats(parent: ET.Element, sheet: SheetInfo, density: str) -> None:
    for conditional_format in sheet.get("conditional_formats", []):
        container = append(parent, "conditional-format", ref=conditional_format.get("ranges"))
        attrs: dict[str, object] = {
            "type": conditional_format.get("ruleType"),
            "priority": conditional_format.get("priority", 0),
            "operator": conditional_format.get("operator"),
            "text": conditional_format.get("text"),
            "dxf": conditional_format.get("dxfId"),
            "style": conditional_format.get("dxfStyle"),
            "stop_if_true": True if conditional_format.get("stopIfTrue") else None,
            "rank": conditional_format.get("rank"),
            "percent": True if conditional_format.get("percent") else None,
            "format": conditional_format.get("formatKind"),
        }
        formulas = conditional_format.get("formulas", [])
        if len(formulas) == 1:
            attrs["formula"] = formulas[0]
        elif formulas:
            attrs["formulas"] = " | ".join(formulas)
        if density == "semantic" and conditional_format.get("formatDetails"):
            attrs["details"] = _conditional_details(conditional_format["formatDetails"])
        append(container, "rule", **attrs)


def _append_pivot_context(parent: ET.Element, metadata: WorkbookMetadata, density: str) -> None:
    for cache in cast(list[dict[str, object]], metadata.get("pivot_caches", [])):
        append(
            parent,
            "pivot-cache",
            id=cache.get("id"),
            cache_id=cache.get("cacheId"),
            sheet=cache.get("sourceSheet"),
            ref=cache.get("sourceRef"),
            refresh_on_load=True if cache.get("refreshOnLoad") else None,
            fields=_joined(cache.get("fields")) if density == "semantic" else None,
        )
    for slicer in cast(list[dict[str, object]], metadata.get("slicers", [])):
        append(
            parent,
            "slicer",
            id=slicer.get("id"),
            name=slicer.get("name"),
            source=slicer.get("sourceName"),
            cache_id=slicer.get("cacheId"),
        )
    for timeline in cast(list[dict[str, object]], metadata.get("timelines", [])):
        append(
            parent,
            "timeline",
            id=timeline.get("id"),
            name=timeline.get("name"),
            source=timeline.get("sourceName"),
            level=timeline.get("level"),
        )


def _append_grid(
    parent: ET.Element,
    rows: list[list[Cell]],
    workbook: ParsedWorkbook,
    density: str,
    *,
    cell_budget: int | None,
) -> None:
    bounds = _visible_bounds(rows)
    if bounds is None:
        return
    min_col, min_row, max_col, max_row = bounds
    visible_rows = [row for row in rows if row]
    emitted: list[list[Cell]] = []
    cell_count = 0
    truncated = False
    for index, row in enumerate(visible_rows):
        cell_count += len(row)
        emitted.append(row)
        if cell_budget is not None and cell_count >= cell_budget:
            truncated = index + 1 < len(visible_rows)
            break
    ref = f"{col_letter(min_col)}{min_row}:{col_letter(max_col)}{max_row}"
    grid = append(parent, "grid", ref=ref, truncated=True if truncated else None)
    format_index = workbook["fmt_index"] if isinstance(workbook["fmt_index"], FormatIndex) else None
    suppressed_styles: set[str] = set()
    if density == "semantic" and format_index is not None:
        records, suppressed_styles = _style_range_records(emitted, format_index)
        for style_ref, attrs in records:
            append(grid, "style-range", ref=style_ref, **attrs)
    comments = _comment_records(emitted)
    comment_ids = _comment_ids_by_cell(comments)
    for row in emitted:
        row_node = append(
            grid,
            "tr",
            number=row[0]["row"],
            hidden=True if row[0].get("hidden") else None,
            outline_level=row[0].get("outlineLevel") if density in {"structural", "semantic"} else None,
            collapsed=True if density in {"structural", "semantic"} and row[0].get("collapsed") else None,
        )
        expected_col = min_col
        for cell in row:
            if cell.get("shadow"):
                continue
            attrs = _cell_attrs(cell, expected_col, density, format_index, suppressed_styles)
            node = append(row_node, "cell", **attrs)
            _append_cell_text(node, cell, density)
            for comment_id in comment_ids.get((cell["row"], cell["col"]), []):
                append(node, "comment-ref", id=comment_id)
            expected_col = cell["col"] + cell.get("colspan", 1)
    if comments:
        group = append(grid, "comments")
        for comment_id, cell, comment in comments:
            append(
                group,
                "comment",
                str(comment.get("text", "")),
                id=comment_id,
                cell=cell["ref"],
                author=comment.get("author"),
                date=comment.get("date"),
                parent=comment.get("parentId"),
                resolved=True if comment.get("resolved") else None,
            )


def _comment_records(rows: list[list[Cell]]) -> list[tuple[str, Cell, dict[str, object]]]:
    records: list[tuple[str, Cell, dict[str, object]]] = []
    legacy_index = 0
    for row in rows:
        for cell in row:
            if cell.get("comment") is not None:
                records.append(
                    (
                        f"comment{legacy_index}",
                        cell,
                        {"text": cell["comment"], "author": cell.get("commentAuthor", "")},
                    )
                )
                legacy_index += 1
            records.extend(
                (str(item.get("id", "")), cell, dict(item)) for item in cell.get("threadedComments", []) if item.get("id")
            )
    return records


def _comment_ids_by_cell(records: list[tuple[str, Cell, dict[str, object]]]) -> dict[tuple[int, int], list[str]]:
    result: dict[tuple[int, int], list[str]] = {}
    for comment_id, cell, _comment in records:
        result.setdefault((cell["row"], cell["col"]), []).append(comment_id)
    return result


def _cell_attrs(
    cell: Cell,
    expected_col: int,
    density: str,
    format_index: FormatIndex | None,
    suppressed_styles: set[str],
) -> dict[str, object]:
    attrs: dict[str, object] = {}
    if cell["col"] != expected_col:
        attrs["column"] = col_letter(cell["col"])
    if density in {"structural", "semantic"}:
        for old, new in (
            ("colspan", "colspan"),
            ("rowspan", "rowspan"),
            ("formula", "formula"),
            ("formulaType", "formula_type"),
            ("formulaRange", "formula_range"),
            ("spillRange", "spill_range"),
            ("spillFrom", "spill_from"),
        ):
            value = cell.get(old)
            if value and (old not in {"colspan", "rowspan"} or value != 1):
                attrs[new] = value
        if cell.get("cellControl"):
            control = cell["cellControl"]
            attrs["control"] = control.get("kind", "unknown")
            attrs["state"] = control.get("state")
            attrs["default"] = control.get("default")
        if cell.get("richValue"):
            rich = cell["richValue"]
            attrs["rich_type"] = rich.get("type", "rich")
            if rich.get("imagePart") or rich.get("imageUrl"):
                attrs["in_cell_image"] = True
                attrs["alt"] = rich.get("alt")
        if format_index is not None and cell.get("style") is not None:
            _add_protection_attrs(attrs, format_index.protection_attrs(cell.get("style")))
    if density == "semantic" and format_index is not None and cell.get("style") is not None:
        style = format_index.style_attrs(cell.get("style"))
        if style and style not in suppressed_styles:
            _add_style_attrs(attrs, style)
    return attrs


def _append_cell_text(parent: ET.Element, cell: Cell, density: str) -> None:
    content_parent = append(parent, "a", href=cell["hyperlink"]) if cell.get("hyperlink") else parent
    rich_value = cell.get("richValue")
    if rich_value and (density == "plain" or rich_value.get("display") or rich_value.get("fallback")):
        text(content_parent, rich_value.get("alt") or rich_value.get("display") or rich_value.get("fallback") or cell["text"])
    elif density == "semantic" and cell.get("rich"):
        for run in cell["rich"]:
            node = content_parent
            if run.get("bold"):
                node = append(node, "b")
            if run.get("italic"):
                node = append(node, "i")
            if run.get("underline"):
                node = append(node, "u")
            if run.get("color"):
                node = append(node, "color", value=run["color"])
            text(node, run.get("text", ""))
    else:
        text(content_parent, cell["text"])


def _visible_bounds(rows: list[list[Cell]]) -> tuple[int, int, int, int] | None:
    min_col = _GRID_BOUND_SENTINEL
    min_row = _GRID_BOUND_SENTINEL
    max_col = 0
    max_row = 0
    for row in rows:
        for cell in row:
            min_col = min(min_col, cell["col"])
            max_col = max(max_col, cell["col"])
            min_row = min(min_row, cell["row"])
            max_row = max(max_row, cell["row"])
    if min_col == _GRID_BOUND_SENTINEL:
        return None
    return min_col, min_row, max_col, max_row


def _add_protection_attrs(attrs: dict[str, object], value: str) -> None:
    for item in value.split():
        if item == "unlocked":
            attrs["locked"] = False
        elif item == "formulaHidden":
            attrs["formula_hidden"] = True


def _add_style_attrs(attrs: dict[str, object], value: str) -> None:
    for item in value.split():
        if item in {"bold", "italic", "underline"}:
            attrs[item] = True
        elif "=" in item:
            key, style_value = item.split("=", 1)
            attrs[key] = style_value


def _chart_names(chart: object) -> list[str]:
    if not isinstance(chart, dict):
        return []
    return [str(item.get("name")) for item in chart.get("series", []) if item.get("name")]


def _joined(value: object) -> str:
    return ",".join(str(item) for item in value) if isinstance(value, list) else ""


def _conditional_details(details: object) -> str:
    if not isinstance(details, dict):
        return ""
    values: list[str] = []
    for key, value in details.items():
        if key in {"stops", "thresholds"} and isinstance(value, list):
            records = [
                ":".join(f"{item_key}={item_value}" for item_key, item_value in item.items())
                for item in value
                if isinstance(item, dict)
            ]
            if records:
                values.append(f"{key}={';'.join(records)}")
            continue
        values.append(f"{key}={value}")
    return ";".join(values)


def _style_range_records(
    rows: list[list[Cell]],
    format_index: FormatIndex,
) -> tuple[list[tuple[str, dict[str, object]]], set[str]]:
    cells_by_style: dict[str, set[tuple[int, int]]] = {}
    for row in rows:
        for cell in row:
            if cell.get("shadow") or cell.get("style") is None:
                continue
            style = format_index.style_attrs(cell.get("style"))
            if "color=" not in style and "fill=" not in style:
                continue
            cells = cells_by_style.setdefault(style, set())
            for row_number in range(cell["row"], cell["row"] + cell.get("rowspan", 1)):
                for column_number in range(cell["col"], cell["col"] + cell.get("colspan", 1)):
                    cells.add((row_number, column_number))
    suppressed = {style for style, cells in cells_by_style.items() if len(cells) >= _STYLE_RANGE_MIN_CELLS}
    records: list[tuple[str, dict[str, object]]] = []
    for style in sorted(suppressed):
        attrs: dict[str, object] = {}
        _add_style_attrs(attrs, style)
        for start_col, first_row, end_col, last_row in _rectangular_ranges(cells_by_style[style]):
            records.append((_range_ref(start_col, first_row, end_col, last_row), attrs))
    return records, suppressed


def _rectangular_ranges(cells: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    spans_by_row = {
        row: _horizontal_spans(sorted(column for item_row, column in cells if item_row == row))
        for row in sorted({item_row for item_row, _column in cells})
    }
    finished: list[tuple[int, int, int, int]] = []
    active: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for row, spans in spans_by_row.items():
        current = set(spans)
        for start_col, end_col in spans:
            key = (start_col, end_col)
            previous = active.get(key)
            if previous is not None and previous[3] == row - 1:
                active[key] = (previous[0], previous[1], previous[2], row)
            else:
                if previous is not None:
                    finished.append(previous)
                active[key] = (start_col, row, end_col, row)
        expired = [key for key in active if key not in current and active[key][3] < row]
        finished.extend(active.pop(key) for key in expired)
    finished.extend(active.values())
    return sorted(finished, key=lambda item: (item[1], item[0], item[3], item[2]))


def _horizontal_spans(columns: list[int]) -> list[tuple[int, int]]:
    if not columns:
        return []
    spans: list[tuple[int, int]] = []
    start = previous = columns[0]
    for column in columns[1:]:
        if column == previous + 1:
            previous = column
            continue
        spans.append((start, previous))
        start = previous = column
    spans.append((start, previous))
    return spans


def _range_ref(start_col: int, start_row: int, end_col: int, end_row: int) -> str:
    start = f"{col_letter(start_col)}{start_row}"
    end = f"{col_letter(end_col)}{end_row}"
    return start if start == end else f"{start}:{end}"


__all__ = ["iter_dtx", "render_sheet_dtx"]
