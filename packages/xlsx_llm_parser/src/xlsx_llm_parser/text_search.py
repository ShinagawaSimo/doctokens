"""Display-text units with original sheet and cell coordinates."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from ooxml_llm_core.text_search import TextSearchOptions, TextSearchResult, TextUnit, search_text

from .models import ParsedWorkbook, ParseOptions
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan
from .rendering.selection import find_sheet


def find_xlsx_text(
    source: str | Path | bytes,
    query: str,
    *,
    options: ParseOptions | None = None,
    search_options: TextSearchOptions | None = None,
    sheets: list[str] | None = None,
) -> TextSearchResult:
    plan = XlsxParsePlan.render("structural")
    if sheets is not None:
        plan = replace(plan, sheet_names=frozenset(sheets))

    def units() -> Iterator[TextUnit]:
        workbook = _parse_workbook(source, options, plan=plan)
        yield from text_units(workbook, sheets)

    return search_text(units(), query, search_options or TextSearchOptions())


def text_units(workbook: ParsedWorkbook, sheets: list[str] | None = None) -> Iterator[TextUnit]:
    selected = workbook["sheets"] if sheets is None else [find_sheet(workbook, name) for name in sheets]
    for sheet in selected:
        for row in sheet.get("rows", []):
            for cell in row:
                if not cell.get("shadow"):
                    yield TextUnit(cell["text"], {"sheet": sheet["name"], "range_spec": cell["ref"]})
