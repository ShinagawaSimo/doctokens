"""Worksheet XML parsing for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import NamedTuple, cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import RelationshipRecord
from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.xml import local_name

from ._sheet_post import (
    apply_comments,
    apply_hyperlinks,
    apply_merge_cells,
    apply_spill_ranges,
    apply_spill_sources,
)
from ._utils import col_letter, parse_ref
from .features import RichValueCatalog
from .formats import FormatIndex
from .models import (
    Cell,
    CellControl,
    ConditionalFormat,
    DataValidation,
    FilterColumn,
    RichTextRun,
)
from .share_formulas import expand_shared_formula_groups

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


@dataclass(slots=True)
class SheetWorkingSet:
    """Row-level IR and indexes accumulated while worksheet XML is streamed."""

    rows: list[list[Cell]] = field(default_factory=list)
    cells_by_coord: dict[tuple[int, int], Cell] = field(default_factory=dict)
    shared_formula_groups: dict[str, list[Cell]] = field(default_factory=dict)
    spill_sources: list[Cell] = field(default_factory=list)

    def add_row(self, cells: list[Cell]) -> None:
        self.rows.append(cells)

    def add_cell(self, cell: Cell) -> None:
        self.cells_by_coord[(cell["col"], cell["row"])] = cell
        si = cell.get("si")
        if si is not None:
            self.shared_formula_groups.setdefault(si, []).append(cell)
        if cell.get("formulaRange") and cell.get("dynamicArray"):
            self.spill_sources.append(cell)

    def finalize(
        self,
        root: ET.Element,
        package: PackageReader,
        sheet_relationships: list[RelationshipRecord],
        threaded_comment_people: Mapping[str, str],
        format_index: FormatIndex | None,
        rich_values: RichValueCatalog,
    ) -> SheetParseResult:
        expand_shared_formula_groups(self.shared_formula_groups)
        apply_merge_cells(root, self.cells_by_coord)
        apply_spill_sources(self.spill_sources, self.cells_by_coord)
        apply_hyperlinks(root, self.cells_by_coord, sheet_relationships, self.rows)
        apply_comments(self.cells_by_coord, package, sheet_relationships, self.rows, threaded_comment_people)
        result = SheetParseResult(
            self.rows,
            _parse_hidden_cols(root),
            root.find(f"{{{NS_S}}}sheetProtection") is not None,
            *_parse_auto_filter(root),
            _parse_data_validations(root),
            _parse_conditional_formats(root, format_index),
        )
        self.cells_by_coord.clear()
        self.shared_formula_groups.clear()
        self.spill_sources.clear()
        return result


class WorksheetScanner:
    """Stream worksheet rows while retaining the existing complete Cell IR."""

    def __init__(
        self,
        package: PackageReader,
        sheet_part: str,
        shared_strings: list[str],
        rich_text_map: dict[int, list[RichTextRun]] | None,
        format_index: FormatIndex | None,
        sheet_relationships: list[RelationshipRecord],
        threaded_comment_people: Mapping[str, str],
        rich_values: RichValueCatalog,
    ) -> None:
        self.package = package
        self.sheet_part = sheet_part
        self.shared_strings = shared_strings
        self.rich_text_map = rich_text_map
        self.format_index = format_index
        self.sheet_relationships = sheet_relationships
        self.threaded_comment_people = threaded_comment_people
        self.rich_values = rich_values

    def parse(self) -> SheetParseResult:
        if not self.package.exists(self.sheet_part):
            return SheetParseResult([], [], False, "", [], [], [])

        working = SheetWorkingSet()
        root: ET.Element | None = None
        current_attrs: RowAttrs | None = None
        current_cells: list[Cell] | None = None
        previous_col = 0
        previous_row = 0
        with self.package.open_entry(self.sheet_part) as stream:
            for event, element in ET.iterparse(stream, events=("start", "end")):
                if event == "start":
                    if root is None:
                        root = element
                    if element.tag == f"{{{NS_S}}}row":
                        raw_attrs = _row_attrs(element)
                        effective_row = raw_attrs.number or previous_row + 1
                        previous_row = effective_row
                        current_attrs = RowAttrs(effective_row, raw_attrs.hidden, raw_attrs.outline_level, raw_attrs.collapsed)
                        current_cells = []
                        previous_col = 0
                    continue
                if element.tag == f"{{{NS_S}}}c" and current_attrs is not None and current_cells is not None:
                    ref = element.get("r", "") or f"{col_letter(previous_col + 1)}{current_attrs.number}"
                    cell = _parse_cell(
                        element,
                        current_attrs,
                        self.shared_strings,
                        self.rich_text_map,
                        self.format_index,
                        ref,
                        self.rich_values,
                    )
                    previous_col = cell["col"]
                    current_cells.append(cell)
                    working.add_cell(cell)
                elif element.tag == f"{{{NS_S}}}row" and current_cells is not None:
                    working.add_row(current_cells)
                    element.clear()
                    current_attrs = None
                    current_cells = None
        if root is None:
            return SheetParseResult([], [], False, "", [], [], [])
        return working.finalize(
            root,
            self.package,
            self.sheet_relationships,
            self.threaded_comment_people,
            self.format_index,
            self.rich_values,
        )


def parse_sheet(
    package: PackageReader,
    sheet_part: str,
    shared_strings: list[str],
    rich_text_map: dict[int, list[RichTextRun]] | None = None,
    format_index: FormatIndex | None = None,
    sheet_relationships: list[RelationshipRecord] | None = None,
    threaded_comment_people: Mapping[str, str] | None = None,
    rich_values: RichValueCatalog | None = None,
) -> SheetParseResult:
    """Parse a worksheet XML part into typed cell rows and sheet-level metadata."""
    return WorksheetScanner(
        package,
        sheet_part,
        shared_strings,
        rich_text_map,
        format_index,
        sheet_relationships or [],
        threaded_comment_people or {},
        rich_values or RichValueCatalog(),
    ).parse()


def _parse_auto_filter(root: ET.Element) -> tuple[str, list[FilterColumn]]:
    filter_range = ""
    filter_cols: list[FilterColumn] = []
    auto_filter = root.find(f"{{{NS_S}}}autoFilter")
    if auto_filter is None:
        return filter_range, filter_cols

    filter_range = auto_filter.get("ref", "")
    for filter_column in auto_filter.findall(f"{{{NS_S}}}filterColumn"):
        column_id = _safe_int(filter_column.get("colId"), 0)
        filter_cols.extend(_parse_filter_column(column_id, filter_column))
    return filter_range, filter_cols


def _parse_filter_column(column_id: int, element: ET.Element) -> list[FilterColumn]:
    """Read every Excel filter form without evaluating the resulting row set."""
    result: list[FilterColumn] = []
    filters = element.find(f"{{{NS_S}}}filters")
    date_group: list[dict[str, str]] = []
    if filters is not None:
        item: FilterColumn = {"col": column_id, "type": "values"}
        values = [child.get("val", "") for child in filters.findall(f"{{{NS_S}}}filter") if child.get("val")]
        date_group.extend(dict(child.attrib) for child in filters.findall(f"{{{NS_S}}}dateGroupItem"))
        if values:
            item["values"] = values
        if filters.get("blank") == "1":
            item["blank"] = True
        if calendar_type := filters.get("calendarType"):
            item["calendarType"] = calendar_type
        if values or item.get("blank") or item.get("calendarType"):
            result.append(item)

    custom = element.find(f"{{{NS_S}}}customFilters")
    if custom is not None:
        for index, rule in enumerate(custom.findall(f"{{{NS_S}}}customFilter")):
            item = {
                "col": column_id,
                "type": "custom",
                "operator": rule.get("operator", "equal"),
                "value": rule.get("val", ""),
            }
            if index == 0 and custom.get("and") == "1":
                item["and"] = True
            result.append(item)

    dynamic = element.find(f"{{{NS_S}}}dynamicFilter")
    if dynamic is not None:
        item = {"col": column_id, "type": "dynamic", "operator": dynamic.get("type", "")}
        for attr_name in ("val", "maxVal"):
            if attr_value := dynamic.get(attr_name):
                item["value" if attr_name == "val" else "value2"] = attr_value
        result.append(item)

    top10 = element.find(f"{{{NS_S}}}top10")
    if top10 is not None:
        item = {
            "col": column_id,
            "type": "top10",
            "top": top10.get("top", "1") == "1",
            "percent": top10.get("percent", "0") == "1",
            "rank": top10.get("val", ""),
        }
        if filter_value := top10.get("filterVal"):
            item["filterValue"] = filter_value
        result.append(item)

    color = element.find(f"{{{NS_S}}}colorFilter")
    if color is not None:
        item = {
            "col": column_id,
            "type": "color",
            "cellColor": color.get("cellColor", "1") == "1",
        }
        if dxf_id := color.get("dxfId"):
            item["dxfId"] = _safe_int(dxf_id, 0)
        result.append(item)

    icon = element.find(f"{{{NS_S}}}iconFilter")
    if icon is not None:
        item = {"col": column_id, "type": "icon"}
        if icon_set := icon.get("iconSet"):
            item["iconSet"] = icon_set
        if icon_id := icon.get("iconId"):
            item["iconId"] = _safe_int(icon_id, 0)
        result.append(item)

    # A few producers place dateGroupItem directly under filterColumn; accept it
    # in addition to the SpreadsheetML-standard location under filters.
    date_group.extend(dict(child.attrib) for child in element.findall(f"{{{NS_S}}}dateGroupItem"))
    if date_group:
        result.append({"col": column_id, "type": "dateGroup", "dateGroup": date_group})
    return result


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


def _parse_conditional_formats(
    root: ET.Element,
    format_index: FormatIndex | None,
) -> list[ConditionalFormat]:
    formats: list[ConditionalFormat] = []
    for conditional_format in root.findall(f"{{{NS_S}}}conditionalFormatting"):
        ranges = conditional_format.get("sqref", "")
        for rule in conditional_format.findall(f"{{{NS_S}}}cfRule"):
            item: ConditionalFormat = {
                "ranges": ranges,
                "priority": _safe_int(rule.get("priority"), 0),
                "ruleType": rule.get("type", ""),
                "formulas": [formula.text or "" for formula in rule.findall(f"{{{NS_S}}}formula")],
                "stopIfTrue": rule.get("stopIfTrue", "0") == "1",
            }
            dxf_id = rule.get("dxfId")
            if dxf_id is not None:
                parsed_dxf_id = _safe_int(dxf_id, 0)
                item["dxfId"] = parsed_dxf_id
                if format_index is not None:
                    dxf_style = format_index.differential_style(parsed_dxf_id)
                    if dxf_style:
                        item["dxfStyle"] = dxf_style
            if operator := rule.get("operator"):
                item["operator"] = operator
            if text := rule.get("text"):
                item["text"] = text
            if rank := rule.get("rank"):
                item["rank"] = _safe_int(rank, 0)
            if rule.get("percent") == "1":
                item["percent"] = True

            detail = _conditional_format_detail(rule)
            if detail is not None:
                item["formatKind"], item["formatDetails"] = detail
            formats.append(item)
    return formats


def _conditional_format_detail(rule: ET.Element) -> tuple[str, dict[str, object]] | None:
    """Capture visual rule semantics without evaluating colors or thresholds."""
    for child in rule:
        name = local_name(child.tag)
        if name == "colorScale":
            stops: list[dict[str, str]] = []
            cfvos = [item for item in child if local_name(item.tag) == "cfvo"]
            colors = [item for item in child if local_name(item.tag) == "color"]
            for index, cfvo in enumerate(cfvos):
                stop = {key: value for key, value in cfvo.attrib.items() if key in {"type", "val", "gte"}}
                if index < len(colors):
                    color = colors[index].get("rgb") or colors[index].get("theme") or colors[index].get("indexed")
                    if color:
                        stop["color"] = color
                stops.append(stop)
            return "colorScale", {"stops": stops}
        if name == "dataBar":
            details: dict[str, object] = {}
            for key in ("minLength", "maxLength", "showValue", "gradient", "border", "direction"):
                value = child.get(key)
                if value is not None:
                    details[key] = value
            color = next(
                (
                    item.get("rgb") or item.get("theme") or item.get("indexed")
                    for item in child
                    if local_name(item.tag) == "color"
                ),
                None,
            )
            if color:
                details["color"] = color
            thresholds = _format_thresholds(child)
            if thresholds:
                details["thresholds"] = thresholds
            return "dataBar", details
        if name == "iconSet":
            icon_details: dict[str, object] = dict(child.attrib)
            thresholds = _format_thresholds(child)
            if thresholds:
                icon_details["thresholds"] = thresholds
            return "iconSet", icon_details
    return None


def _format_thresholds(parent: ET.Element) -> list[dict[str, str]]:
    return [
        {key: value for key, value in item.attrib.items() if key in {"type", "val", "gte"}}
        for item in parent
        if local_name(item.tag) == "cfvo"
    ]


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


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
    prev_row = 0
    for row_elem in sheet_data.findall(f"{{{NS_S}}}row"):
        row_attrs = _row_attrs(row_elem)
        effective_row = row_attrs.number or prev_row + 1
        prev_row = effective_row
        row_cells: list[Cell] = []
        prev_col = 0
        for cell_elem in row_elem.findall(f"{{{NS_S}}}c"):
            ref = cell_elem.get("r", "")
            if not ref:
                # Some writers omit r; inherit the previous cell's position.
                ref = f"{col_letter(prev_col + 1)}{effective_row}"
            cell = _parse_cell(cell_elem, row_attrs, shared_strings, rich_text_map, format_index, ref)
            prev_col = cell["col"]
            row_cells.append(cell)
        rows.append(row_cells)
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
    ref: str,
    rich_values: RichValueCatalog | None = None,
) -> Cell:
    col, row = parse_ref(ref)
    cell_type = cell_elem.get("t", "n")
    text, value_elem = _cell_text(cell_elem, cell_type, shared_strings)
    text = _formatted_text(cell_elem, cell_type, text, format_index)
    formula, formula_meta = _formula_metadata(cell_elem)

    cell: Cell = {"ref": ref, "row": row_attrs.number or row, "col": col, "text": text}
    _apply_row_attrs(cell, row_attrs)
    _attach_rich_text(cell, cell_type, value_elem, rich_text_map)
    _attach_style(cell, cell_elem)
    if rich_values is not None and (rich_value := rich_values.resolve(cell_elem.get("vm"))):
        cell["richValue"] = rich_value
    if format_index is not None:
        style_index = cell.get("style")
        if control := format_index.cell_control(style_index):
            control_data = cast(CellControl, dict(control))
            cell["cellControl"] = control_data
            if control.get("kind") == "checkbox":
                control_data["value"] = text
                control_data["state"] = {"true": "true", "false": "false", "": "empty"}.get(text, "empty")
    if formula is not None:
        cell["formula"] = formula
    cell.update(formula_meta)

    semantic_type = _CELL_TYPE_MAP.get(cell_type)
    if semantic_type and semantic_type != "number":
        cell["type"] = semantic_type
    if cell.get("richValue", {}).get("imagePart") or cell.get("richValue", {}).get("imageUrl"):
        cell["type"] = "image"
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
        if formula_elem.get("aca") == "1":
            # aca marks true dynamic-array formulas; classic CSE arrays share
            # the t="array"/ref shape but do not spill.
            metadata["dynamicArray"] = True
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
    apply_hyperlinks(root, cell_map, sheet_rels, rows)
    apply_comments(cell_map, pkg, sheet_rels, rows)
