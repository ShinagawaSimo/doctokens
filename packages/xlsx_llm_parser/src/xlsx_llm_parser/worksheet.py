"""Worksheet XML parsing for XLSX workbooks."""

from __future__ import annotations

from contextlib import suppress
from typing import NamedTuple
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ._sheet_post import (
    apply_comments,
    apply_hyperlinks,
    apply_merge_cells,
    apply_spill_ranges,
)
from ._utils import parse_ref
from .formats import FormatIndex
from .models import (
    Cell,
    ConditionalFormat,
    DataValidation,
    FilterColumn,
    RichTextRun,
)
from .share_formulas import expand_shared_formulas

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

_CELL_TYPE_MAP: dict[str, str] = {
    "n": "number",
    "s": "string",
    "inlineStr": "string",
    "str": "string",
    "b": "boolean",
    "e": "error",
    "d": "date",
}


class SheetParseResult(NamedTuple):
    rows: list[list[Cell]]
    hidden_cols: list[tuple[int, int]]
    sheet_protection: bool
    filter_range: str
    filter_cols: list[FilterColumn]
    data_validations: list[DataValidation]
    conditional_formats: list[ConditionalFormat]


class RowAttrs(NamedTuple):
    number: int
    hidden: bool
    outline_level: int
    collapsed: bool


def parse_sheet(
    package: PackageReader,
    sheet_part: str,
    shared_strings: list[str],
    rich_text_map: dict[int, list[RichTextRun]] | None = None,
    format_index: FormatIndex | None = None,
    sheet_relationships: list[RelationshipRecord] | None = None,
) -> SheetParseResult:
    """Parse a worksheet XML part into typed cell rows and sheet-level metadata."""
    if not package.exists(sheet_part):
        return SheetParseResult([], [], False, "", [], [], [])

    with package.open_entry(sheet_part) as stream:
        root = ET.parse(stream).getroot()

    sheet_protection = root.find(f"{{{NS_S}}}sheetProtection") is not None
    filter_range, filter_cols = _parse_auto_filter(root)
    data_validations = _parse_data_validations(root)
    conditional_formats = _parse_conditional_formats(root)
    hidden_cols = _parse_hidden_cols(root)
    rows = _parse_rows(root, shared_strings, rich_text_map, format_index)

    # Expand shared formulas in-place before post-processing.
    flat_cells = [cell for row_cells in rows for cell in row_cells]
    expand_shared_formulas(flat_cells)

    _post_process_rows(root, rows, package, sheet_relationships or [])

    return SheetParseResult(
        rows,
        hidden_cols,
        sheet_protection,
        filter_range,
        filter_cols,
        data_validations,
        conditional_formats,
    )


def _parse_auto_filter(root: ET.Element) -> tuple[str, list[FilterColumn]]:
    filter_range = ""
    filter_cols: list[FilterColumn] = []
    auto_filter = root.find(f"{{{NS_S}}}autoFilter")
    if auto_filter is None:
        return filter_range, filter_cols

    filter_range = auto_filter.get("ref", "")
    for filter_column in auto_filter.findall(f"{{{NS_S}}}filterColumn"):
        column_id = int(filter_column.get("colId", "0"))
        filters = filter_column.find(f"{{{NS_S}}}filters")
        if filters is None:
            continue
        values = [item.get("val", "") for item in filters.findall(f"{{{NS_S}}}filter") if item.get("val")]
        if values:
            filter_cols.append({"col": column_id, "type": "values", "values": values})
    return filter_range, filter_cols


def _parse_data_validations(root: ET.Element) -> list[DataValidation]:
    validations = root.find(f"{{{NS_S}}}dataValidations")
    if validations is None:
        return []
    return [
        {
            "ranges": item.get("sqref", ""),
            "type": item.get("type", ""),
            "formula1": item.findtext(f"{{{NS_S}}}formula1", ""),
            "allowBlank": item.get("allowBlank", "1") == "1",
        }
        for item in validations.findall(f"{{{NS_S}}}dataValidation")
    ]


def _parse_conditional_formats(root: ET.Element) -> list[ConditionalFormat]:
    formats: list[ConditionalFormat] = []
    for conditional_format in root.findall(f"{{{NS_S}}}conditionalFormatting"):
        ranges = conditional_format.get("sqref", "")
        formats.extend(
            {
                "ranges": ranges,
                "priority": int(rule.get("priority", "0")),
                "ruleType": rule.get("type", ""),
                "formula": rule.findtext(f"{{{NS_S}}}formula", ""),
            }
            for rule in conditional_format.findall(f"{{{NS_S}}}cfRule")
        )
    return formats


def _parse_hidden_cols(root: ET.Element) -> list[tuple[int, int]]:
    cols = root.find(f"{{{NS_S}}}cols")
    if cols is None:
        return []

    hidden_cols: list[tuple[int, int]] = []
    for col in cols.findall(f"{{{NS_S}}}col"):
        if col.get("hidden") != "1":
            continue
        min_col = int(col.get("min", "1"))
        max_col = int(col.get("max", str(min_col)))
        hidden_cols.append((min_col, max_col))
    return hidden_cols


def _parse_rows(
    root: ET.Element,
    shared_strings: list[str],
    rich_text_map: dict[int, list[RichTextRun]] | None,
    format_index: FormatIndex | None,
) -> list[list[Cell]]:
    sheet_data = root.find(f"{{{NS_S}}}sheetData")
    if sheet_data is None:
        return []

    rows: list[list[Cell]] = []
    for row_elem in sheet_data.findall(f"{{{NS_S}}}row"):
        row_attrs = _row_attrs(row_elem)
        rows.append(
            [
                _parse_cell(cell_elem, row_attrs, shared_strings, rich_text_map, format_index)
                for cell_elem in row_elem.findall(f"{{{NS_S}}}c")
            ]
        )
    return rows


def _row_attrs(row_elem: ET.Element) -> RowAttrs:
    outline_level_str = row_elem.get("outlineLevel")
    return RowAttrs(
        number=int(row_elem.get("r", "0")),
        hidden=row_elem.get("hidden") == "1",
        outline_level=int(outline_level_str) if outline_level_str else 0,
        collapsed=row_elem.get("collapsed") == "1",
    )


def _parse_cell(
    cell_elem: ET.Element,
    row_attrs: RowAttrs,
    shared_strings: list[str],
    rich_text_map: dict[int, list[RichTextRun]] | None,
    format_index: FormatIndex | None,
) -> Cell:
    ref = cell_elem.get("r", "")
    col, row = parse_ref(ref)
    cell_type = cell_elem.get("t", "n")
    text, value_elem = _cell_text(cell_elem, cell_type, shared_strings)
    text = _formatted_text(cell_elem, cell_type, text, format_index)
    formula, formula_meta = _formula_metadata(cell_elem)

    cell: Cell = {"ref": ref, "row": row_attrs.number or row, "col": col, "text": text}
    _apply_row_attrs(cell, row_attrs)
    _attach_rich_text(cell, cell_type, value_elem, rich_text_map)
    _attach_style(cell, cell_elem)
    if formula is not None:
        cell["formula"] = formula
    cell.update(formula_meta)

    semantic_type = _CELL_TYPE_MAP.get(cell_type)
    if semantic_type and semantic_type != "number":
        cell["type"] = semantic_type
    return cell


def _cell_text(
    cell_elem: ET.Element,
    cell_type: str,
    shared_strings: list[str],
) -> tuple[str, ET.Element | None]:
    if cell_type == "inlineStr":
        inline_text = cell_elem.find(f"{{{NS_S}}}is/{{{NS_S}}}t")
        return (inline_text.text or "", None) if inline_text is not None else ("", None)

    value_elem = cell_elem.find(f"{{{NS_S}}}v")
    if value_elem is None or not value_elem.text:
        return "", value_elem

    if cell_type == "s":
        with suppress(ValueError):
            idx = int(value_elem.text)
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx], value_elem
        return "", value_elem

    if cell_type == "b":
        return ("true" if value_elem.text == "1" else "false"), value_elem
    return value_elem.text, value_elem


def _formatted_text(
    cell_elem: ET.Element,
    cell_type: str,
    text: str,
    format_index: FormatIndex | None,
) -> str:
    if format_index is None or cell_type != "n" or not text:
        return text
    style_str = cell_elem.get("s")
    if style_str is None:
        return text
    with suppress(ValueError, IndexError):
        return format_index.format_value(int(style_str), text)
    return text


def _formula_metadata(cell_elem: ET.Element) -> tuple[str | None, Cell]:
    formula_elem = cell_elem.find(f"{{{NS_S}}}f")
    if formula_elem is None:
        return None, {}

    formula = formula_elem.text or None
    formula_type = formula_elem.get("t", "")
    metadata: Cell = {}
    if formula_type == "shared":
        shared_index = formula_elem.get("si")
        shared_ref = formula_elem.get("ref")
        if shared_ref:
            metadata["shared_ref"] = shared_ref
        if shared_index is not None:
            metadata["si"] = shared_index
    elif formula_type == "array":
        metadata["formulaType"] = "array"
        formula_range = formula_elem.get("ref", "")
        if formula_range:
            metadata["formulaRange"] = formula_range
    elif formula_type == "dataTable":
        metadata["formulaType"] = "dataTable"
    return formula, metadata


def _apply_row_attrs(cell: Cell, row_attrs: RowAttrs) -> None:
    if row_attrs.hidden:
        cell["hidden"] = True
    if not row_attrs.outline_level:
        return
    cell["outlineLevel"] = row_attrs.outline_level
    if row_attrs.collapsed:
        cell["collapsed"] = True


def _attach_rich_text(
    cell: Cell,
    cell_type: str,
    value_elem: ET.Element | None,
    rich_text_map: dict[int, list[RichTextRun]] | None,
) -> None:
    if rich_text_map is None or cell_type != "s" or value_elem is None or not value_elem.text:
        return
    with suppress(ValueError):
        idx = int(value_elem.text)
        if idx in rich_text_map:
            cell["rich"] = rich_text_map[idx]


def _attach_style(cell: Cell, cell_elem: ET.Element) -> None:
    style_str = cell_elem.get("s")
    if style_str is None:
        return
    with suppress(ValueError):
        cell["style"] = int(style_str)


def _post_process_rows(
    root: ET.Element,
    rows: list[list[Cell]],
    pkg: PackageReader,
    sheet_rels: list[RelationshipRecord],
) -> None:
    cell_map = {(cell["col"], cell["row"]): cell for row_cells in rows for cell in row_cells}
    apply_merge_cells(root, cell_map)
    apply_spill_ranges(rows, cell_map)
    apply_hyperlinks(root, cell_map, sheet_rels)
    apply_comments(cell_map, pkg, sheet_rels)
