"""Direct DTX serialization for XLSX parsed workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.doctokens_xml import append, element, serialize, text

from .._utils import col_letter
from ..models import Cell, ParsedWorkbook, SheetInfo
from ..parsing.modules.styles.index import FormatIndex
from ._constants import _CELL_BUDGET, _GRID_BOUND_SENTINEL
from .dtx_metadata import _add_protection_attrs, _append_sheet_metadata, _append_workbook_metadata
from .style_ranges import _add_style_attrs, _style_range_records


def iter_dtx(parsed_workbook: ParsedWorkbook, density: str) -> Iterator[str]:
    """Yield one DTX workbook directly from parsed worksheet IR."""
    root = element("workbook", density=density, format="xlsx")
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
    root = element("workbook", density=density, format="xlsx")
    selected = cast(SheetInfo, dict(sheet))
    if rows is not None:
        selected["rows"] = rows
    _append_sheet(root, selected, parsed_workbook, density, emit_globals=True, cell_budget=None)
    return serialize(root)


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
    data_table_groups: set[tuple[str, str]] = set()
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
            if cell.get("formulaType") == "dataTable" and cell.get("formula") and cell.get("formulaRange"):
                data_table_key = (cell["formulaRange"], cell["formula"])
                if data_table_key in data_table_groups:
                    for attr in ("formula", "formula_type", "formula_range"):
                        attrs.pop(attr, None)
                else:
                    data_table_groups.add(data_table_key)
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
        raw = cell.get("raw")
        if raw is not None and raw != cell.get("text", ""):
            attrs["raw"] = raw
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
    if density == "semantic" and cell.get("numberFormatColor"):
        attrs["color"] = cell["numberFormatColor"]
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


__all__ = ["iter_dtx", "render_sheet_dtx"]
