"""Shared public body-selection projection for one-shot and session reads."""

from __future__ import annotations

from ooxml_llm_core.doctokens_plain import render_plain
from ooxml_llm_core.models import ParseResult

from ._api_support import _result
from .models import ParsedWorkbook
from .parsing import get_render_pipeline
from .rendering.dtx import render_sheet_dtx
from .rendering.plain import iter_plain_window
from .rendering.window import reading_window
from .search import _sheet


def render_selection(workbook: ParsedWorkbook, density: str, sheet: str | None, range_spec: str | None) -> ParseResult:
    if range_spec is not None and sheet is None:
        raise ValueError("range_spec requires sheet")
    if sheet is None:
        text = "".join(get_render_pipeline(density).render(workbook))
        selection: dict[str, object] = {
            "kind": "all",
            "windows": [reading_window(item, density).metadata for item in workbook["sheets"]],
        }
    else:
        sheet_info = _sheet(workbook, sheet)
        if range_spec is not None and sheet_info.get("kind") == "chartsheet":
            raise ValueError("range_spec requires a worksheet, not a chartsheet")
        window = reading_window(sheet_info, density, range_spec=range_spec)
        if density == "plain":
            text = render_plain("density=plain\n" + "".join(iter_plain_window(window, sheet_info)), format_name="xlsx")
        else:
            text = render_sheet_dtx(workbook, sheet_info, density, window=window)
        selection = {"kind": "range" if range_spec is not None else "sheet", "sheet": sheet, "windows": [window.metadata]}
        if range_spec is not None:
            selection["ref"] = range_spec
    return _result(workbook, text, density, selection)
