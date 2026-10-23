"""Display-text units with original sheet and cell coordinates."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ooxml_llm_core.text_search import TextSearchCollector, TextSearchOptions, TextSearchResult, TextUnit

from ._operation_source import OperationSource
from ._utils import parse_ref
from .models import Cell, ParsedWorkbook, ParseOptions
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
    collector = TextSearchCollector(query, search_options or TextSearchOptions())
    with OperationSource(source, options) as opened:
        selected = opened.sheets if sheets is None else [find_sheet(opened.workbook(), name) for name in sheets]
        for sheet in selected:
            bounds = (1, 1, 16_384, 1_048_576)
            preflight = opened.preflight(sheet, bounds, None, annotations=False)
            plan = XlsxParsePlan.values(sheet["name"])
            if not preflight.ordered_rows:
                fallback = opened.scan(sheet, XlsxParsePlan.values(sheet["name"], annotations=True))
                for row in fallback.rows:
                    for cell in row:
                        if not cell.get("shadow") and not collector.consume(
                            TextUnit(cell["text"], {"sheet": sheet["name"], "range_spec": cell["ref"]})
                        ):
                            break
                if collector.complete:
                    break
                continue
            merges = [
                (parse_ref(first), parse_ref(last))
                for ref in preflight.merge_refs
                if ":" in ref
                for first, last in [ref.split(":", 1)]
            ]

            def consume(
                _number: int,
                cells: list[Cell],
                name: str = sheet["name"],
                regions: list[tuple[tuple[int, int], tuple[int, int]]] = merges,
            ) -> bool:
                for cell in sorted(cells, key=lambda item: item["col"]):
                    if any(
                        left <= cell["col"] <= right
                        and top <= cell["row"] <= bottom
                        and (cell["col"], cell["row"]) != (left, top)
                        for (left, top), (right, bottom) in regions
                    ):
                        continue
                    if not collector.consume(TextUnit(cell["text"], {"sheet": name, "range_spec": cell["ref"]})):
                        return False
                return True

            opened.scan(sheet, plan, row_sink=consume)
            if collector.complete:
                break
    return collector.result()


def text_units(workbook: ParsedWorkbook, sheets: list[str] | None = None) -> Iterator[TextUnit]:
    selected = workbook["sheets"] if sheets is None else [find_sheet(workbook, name) for name in sheets]
    for sheet in selected:
        for row in sheet.get("rows", []):
            for cell in row:
                if not cell.get("shadow"):
                    yield TextUnit(cell["text"], {"sheet": sheet["name"], "range_spec": cell["ref"]})
