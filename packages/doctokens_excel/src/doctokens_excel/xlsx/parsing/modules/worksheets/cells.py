"""Cells."""

from __future__ import annotations

from contextlib import suppress
from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.cell import CompactCell
from ....model.coordinates import parse_ref
from ....model.workbook import Cell, CellControl, RichTextRun
from ..styles.index import FormatIndex
from ..workbook.rich_values import RichValueCatalog
from ..workbook.shared_strings import SharedStrings
from ..workbook.string_text import WarningSink, decode_xstring, read_string
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
        style=(_style_index(row_elem) or 0) if row_elem.get("customFormat", "false").lower() in {"1", "true"} else None,
    )


def _parse_cell(
    cell_elem: ET.Element,
    row_attrs: RowAttrs,
    shared_strings: SharedStrings,
    rich_text_map: dict[int, list[RichTextRun]] | None,
    format_index: FormatIndex | None,
    ref: str,
    rich_values: RichValueCatalog | None = None,
    *,
    warnings: list[ParseWarning],
    sheet_part: str,
    column_style: int | None,
    include_rich_text: bool,
    include_style_index: bool,
    include_semantic_style: bool,
    include_formulas: bool,
    include_cell_controls: bool,
    include_display_text: bool = True,
    coordinates: tuple[int, int] | None = None,
    formula_element: ET.Element | None = None,
    decoded: bool = False,
) -> Cell:
    col, row = coordinates if coordinates is not None else parse_ref(ref)
    style_index = effective_style(cell_elem, row_attrs, column_style)
    formula_element = formula_element if decoded else cell_elem.find(f"{{{NS_S}}}f")
    cell_type = cell_elem.get("t", "n")
    text, value_elem, inline_rich = (
        _cell_text(
            cell_elem,
            cell_type,
            shared_strings,
            rich=include_rich_text,
            warn=lambda code, message: warnings.append(ParseWarning(code, message, f"{sheet_part}!{ref}")),
        )
        if include_display_text
        else ("", None, None)
    )
    formula, formula_meta = _formula_metadata(formula_element) if include_formulas else (None, {})
    source_text = text
    if include_display_text:
        text = _formatted_text(style_index, cell_type, text, format_index)

    cell: Cell = {"ref": ref, "row": row_attrs.number or row, "col": col, "text": text}
    if _blank_candidate(cell_elem, cell_type, value_elem, row_attrs, style_index, format_index):
        cell["blankCandidate"] = True
    _apply_row_attrs(cell, row_attrs)
    if include_rich_text:
        if inline_rich is not None:
            cell["rich"] = inline_rich
        else:
            _attach_rich_text(cell, cell_type, value_elem, rich_text_map)
    if include_display_text and cell_type in {"s", "str", "inlineStr"} and format_index is not None:
        _format_text_cell(cell, source_text, format_index.text_format_parts(style_index))
    if include_style_index and formula_element is None:
        _attach_formula_bar_value(cell, style_index, cell_type, source_text, format_index)
    if include_semantic_style and format_index is not None and cell_type in {"n", "s", "str", "inlineStr"}:
        color = format_index.number_format_color(style_index, source_text, is_text=cell_type != "n")
        if color:
            cell["numberFormatColor"] = color
    if (include_style_index or include_semantic_style) and style_index is not None:
        cell["style"] = style_index
    if rich_values is not None and (rich_value := rich_values.resolve(cell_elem.get("vm"))):
        cell["richValue"] = rich_value
    if include_cell_controls and format_index is not None and (control := format_index.cell_control(style_index)):
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
    # Decode into a short-lived dict; compact only the retained result so the
    # field-attachment helpers keep native dictionary access on this hot path.
    return cast(Cell, CompactCell(cell))


def _blank_candidate(
    cell_elem: ET.Element,
    cell_type: str,
    value_elem: ET.Element | None,
    row_attrs: RowAttrs,
    style_index: int | None,
    format_index: FormatIndex | None,
) -> bool:
    return (
        cell_type == "n"
        and (value_elem is None or not value_elem.text)
        and not any(child.tag in {f"{{{NS_S}}}is", f"{{{NS_S}}}f"} for child in cell_elem)
        and cell_elem.get("vm") is None
        and cell_elem.get("cm") is None
        and (format_index is not None and not format_index.preserves_blank(style_index))
        and not format_index.preserves_blank(row_attrs.style)
    )


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
    style_index: int | None,
    cell_type: str,
    source: str,
    format_index: FormatIndex | None,
) -> None:
    if not source:
        return
    if cell_type in {"s", "inlineStr", "str", "b", "e"}:
        cell["raw"] = source
        return
    raw = None
    if cell_type == "n":
        index = format_index if format_index is not None else FormatIndex()
        raw = index.formula_bar_value(style_index, source)
    if raw is not None:
        cell["raw"] = cell["text"] if raw == cell["text"] else raw


def _style_index(cell_elem: ET.Element) -> int | None:
    with suppress(ValueError):
        return int(cell_elem.get("s", ""))
    return None


def _cell_text(
    cell_elem: ET.Element,
    cell_type: str,
    shared_strings: SharedStrings,
    *,
    rich: bool,
    warn: WarningSink,
) -> tuple[str, ET.Element | None, list[RichTextRun] | None]:
    if cell_type == "inlineStr":
        value, runs = read_string(cell_elem.find(f"{{{NS_S}}}is"), rich=rich, warn=warn)
        return value, None, runs

    value_elem = cell_elem.find(f"{{{NS_S}}}v")
    if value_elem is None or not value_elem.text:
        return "", value_elem, None

    if cell_type == "s":
        with suppress(ValueError):
            idx = int(value_elem.text)
            if isinstance(shared_strings, dict):
                return shared_strings.get(idx, ""), value_elem, None
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx], value_elem, None
        return "", value_elem, None

    if cell_type == "b":
        return ("TRUE" if value_elem.text == "1" else "FALSE"), value_elem, None
    return decode_xstring(value_elem.text, warn) if cell_type == "str" else value_elem.text, value_elem, None


def effective_style(cell: ET.Element, row: RowAttrs, column_style: int | None) -> int:
    direct = _style_index(cell)
    return (
        direct if direct is not None else row.style if row.style is not None else column_style if column_style is not None else 0
    )


def _formatted_text(
    style_index: int | None,
    cell_type: str,
    text: str,
    format_index: FormatIndex | None,
) -> str:
    if format_index is None or cell_type != "n" or not text:
        return text
    if style_index is None:
        return text
    with suppress(ValueError, IndexError):
        return format_index.format_value(style_index, text)
    return text


def _formula_metadata(formula_elem: ET.Element | None) -> tuple[str | None, Cell]:
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
