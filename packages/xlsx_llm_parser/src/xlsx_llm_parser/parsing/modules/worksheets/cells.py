"""Cells."""

from __future__ import annotations

from contextlib import suppress
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ...._utils import parse_ref
from ....models import (
    Cell,
    CellControl,
    RichTextRun,
)
from ..styles.index import FormatIndex
from ..workbook.rich_values import RichValueCatalog
from .sheet_types import NS_S, RowAttrs

_CELL_TYPE_MAP: dict[str, str] = {
    "n": "number",
    "s": "string",
    "inlineStr": "string",
    "str": "string",
    "b": "boolean",
    "e": "error",
    "d": "date",
}


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
    *,
    include_rich_text: bool,
    include_style_index: bool,
    include_semantic_style: bool,
    include_formulas: bool,
    include_cell_controls: bool,
    warnings: list[ParseWarning] | None = None,
    sheet_part: str = "",
) -> Cell:
    col, row = parse_ref(ref)
    cell_type = cell_elem.get("t", "n")
    text, value_elem = _cell_text(cell_elem, cell_type, shared_strings)
    formula, formula_meta = _formula_metadata(cell_elem) if include_formulas else (None, {})
    source_text = text
    text = _formatted_text(cell_elem, cell_type, text, format_index)

    cell: Cell = {"ref": ref, "row": row_attrs.number or row, "col": col, "text": text}
    _apply_row_attrs(cell, row_attrs)
    if include_rich_text:
        _attach_rich_text(cell, cell_type, value_elem, rich_text_map)
    if cell_type in {"s", "str", "inlineStr"} and format_index is not None:
        _format_text_cell(cell, source_text, format_index.text_format_parts(_style_index(cell_elem)))
    if include_style_index and cell_elem.find(f"{{{NS_S}}}f") is None:
        _attach_formula_bar_value(cell, cell_elem, cell_type, source_text, format_index, warnings, sheet_part)
    if include_semantic_style and format_index is not None and cell_type in {"n", "s", "str", "inlineStr"}:
        color = format_index.number_format_color(_style_index(cell_elem), source_text, is_text=cell_type != "n")
        if color:
            cell["numberFormatColor"] = color
    if include_style_index:
        _attach_style_index(cell, cell_elem)
    if include_semantic_style:
        _attach_style(cell, cell_elem)
    if rich_values is not None and (rich_value := rich_values.resolve(cell_elem.get("vm"))):
        cell["richValue"] = rich_value
    if include_cell_controls and format_index is not None:
        style_index = cell.get("style") if include_semantic_style else _style_index(cell_elem)
        if control := format_index.cell_control(style_index):
            control_data = cast(CellControl, dict(control))
            cell["cellControl"] = control_data
            if control.get("kind") == "checkbox":
                control_data["value"] = text
                control_data["state"] = {"TRUE": "true", "FALSE": "false", "": "empty"}.get(text, "empty")
    if formula is not None:
        cell["formula"] = formula
    cell.update(formula_meta)

    semantic_type = _CELL_TYPE_MAP.get(cell_type)
    if semantic_type and semantic_type != "number":
        cell["type"] = semantic_type
    if cell.get("richValue", {}).get("imagePart") or cell.get("richValue", {}).get("imageUrl"):
        cell["type"] = "image"
    return cell


def _format_text_cell(cell: Cell, source: str, parts: list[str | None] | None) -> None:
    if parts is None:
        return
    cell["text"] = "".join(source if part is None else part for part in parts)
    if "rich" in cell:
        # Do not mutate the shared-string catalog or lose the original runs.
        source_runs = cell["rich"]
        rendered_runs: list[RichTextRun] = []
        for part in parts:
            if part is None:
                rendered_runs.extend(source_runs)
            elif part:
                rendered_runs.append({"text": part})
        cell["rich"] = rendered_runs


def _attach_formula_bar_value(
    cell: Cell,
    element: ET.Element,
    cell_type: str,
    source: str,
    format_index: FormatIndex | None,
    warnings: list[ParseWarning] | None,
    sheet_part: str,
) -> None:
    if not source:
        return
    if cell_type in {"s", "inlineStr", "str", "b", "e"}:
        cell["raw"] = source
        return
    raw = None
    if cell_type == "n":
        index = format_index if format_index is not None else FormatIndex()
        raw = index.formula_bar_value(_style_index(element), source)
    if raw is not None:
        cell["raw"] = raw
    elif warnings is not None and cell.get("text") != source:
        warnings.append(
            ParseWarning(
                "XLSX_FORMULA_BAR_UNAVAILABLE",
                "Formula-bar content cannot be reliably reconstructed; raw is omitted and cell display is retained.",
                f"{sheet_part}!{cell['ref']}",
            )
        )


def _style_index(cell_elem: ET.Element) -> int | None:
    with suppress(ValueError):
        return int(cell_elem.get("s", ""))
    return None


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
        return ("TRUE" if value_elem.text == "1" else "FALSE"), value_elem
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
        if formula_range := formula_elem.get("ref", ""):
            metadata["formulaRange"] = formula_range
        # The worksheet pass reconstructs TABLE from its master's attributes.
        formula = None
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


def _attach_style_index(cell: Cell, cell_elem: ET.Element) -> None:
    """Keep the cell-XF index without materializing semantic style details."""
    style_str = cell_elem.get("s")
    if style_str is None:
        return
    with suppress(ValueError):
        cell["style"] = int(style_str)
