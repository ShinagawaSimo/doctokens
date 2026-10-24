"""Explicit, resumable XLSX displayed text; retention belongs to its caller."""

from __future__ import annotations

from collections.abc import Generator, Iterator

from ooxml_llm_core.memory import object_bytes
from ooxml_llm_core.text_search import TextUnit

from ._api_support import Source
from ._operation_source import OperationSource
from ._utils import parse_ref
from .models import Cell, ParseOptions, SheetInfo
from .parsing.modules.worksheets.value_rows import iter_value_rows
from .plan import XlsxParsePlan
from .rendering.selection import find_sheet


class XlsxTextSource:
    def __init__(self, source: Source, *, options: ParseOptions | None = None, sheets: list[str] | None = None) -> None:
        self.source, self.options, self.sheets = source, options, sheets
        self._opened: OperationSource | None = None
        self._iterator: Generator[TextUnit, None, None] | None = None
        self._base_bytes = 0
        self._row: list[Cell] = []
        self._state = "new"
        self._metadata_bytes = 0
        self._program_bytes = 0
        self._program_key: tuple[tuple[int, int, int, int], ...] = ()

    def __enter__(self) -> XlsxTextSource:
        if self._state != "new":
            raise RuntimeError("XLSX text source cannot be entered twice")
        opened = OperationSource(self.source, self.options)
        try:
            opened.__enter__()
            selected = opened.sheets if self.sheets is None else [find_sheet(opened.workbook(), name) for name in self.sheets]
            self._base_bytes = 1024 * 1024 + 2 * object_bytes((opened.strings, opened.rich, vars(opened.formats), selected))
            self._opened = opened
            self._iterator = self._units(opened, selected)
        except BaseException:
            opened.__exit__(None, None, None)
            self.close()
            raise
        self._state = "open"
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def estimated_memory_bytes(self) -> int:
        if self._opened is None:
            return 0
        programs = self._opened.formats._programs.values()
        key = tuple((id(p), len(p._dates), len(p._syntax), len(p._classifications)) for p in programs)
        if key != self._program_key:
            self._program_bytes = 2 * object_bytes([vars(p) for p in programs])
            self._program_key = key
        return (
            self._base_bytes
            + self._metadata_bytes
            + self._program_bytes
            + 65536
            + 2 * object_bytes(self._row)
            + self._opened.package._part_cache_bytes
        )

    def __iter__(self) -> Iterator[TextUnit]:
        if self._state != "open" or self._iterator is None:
            raise RuntimeError("XLSX text source is not open")
        return self._iterator

    def close(self) -> None:
        if self._iterator is not None:
            self._iterator.close()
        if self._opened is not None:
            self._opened.__exit__(None, None, None)
        self._iterator = self._opened = None
        self._base_bytes = 0
        self._row = []
        self._state = "closed"

    def _units(self, opened: OperationSource, selected: list[SheetInfo]) -> Generator[TextUnit, None, None]:
        for sheet in selected:
            if sheet.get("kind") == "chartsheet":
                continue
            preflight = opened.preflight(sheet, (1, 1, 16_384, 1_048_576), None, annotations=False)
            merges = [
                (parse_ref(first), parse_ref(last))
                for ref in preflight.merge_refs
                if ":" in ref
                for first, last in [ref.split(":", 1)]
            ]
            self._metadata_bytes = 2 * object_bytes((opened._relationships, preflight, merges))
            rows: Iterator[list[Cell]]
            if preflight.ordered_rows:
                rows = iter_value_rows(opened.package, sheet["part"], opened.strings, opened.formats)
            else:
                fallback = opened.scan(sheet, XlsxParsePlan.values(sheet["name"], annotations=True))
                self._base_bytes += 2 * object_bytes(fallback.rows)
                rows = iter(fallback.rows)
            try:
                for row in rows:
                    self._row = row
                    for cell in sorted(row, key=lambda item: item["col"]):
                        if cell.get("shadow") or any(
                            left <= cell["col"] <= right
                            and top <= cell["row"] <= bottom
                            and (cell["col"], cell["row"]) != (left, top)
                            for (left, top), (right, bottom) in merges
                        ):
                            continue
                        yield TextUnit(cell["text"], {"sheet": sheet["name"], "range_spec": cell["ref"]})
            finally:
                close = getattr(rows, "close", None)
                if close is not None:
                    close()
