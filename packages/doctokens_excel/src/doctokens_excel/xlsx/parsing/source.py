"""Explicit package ownership and display-only inputs for XLSX data operations."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from time import perf_counter
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.limits import PackageLimits
from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.contracts.models import ParseReport, ParseResult, ParseWarning, Source

from ..model.workbook import Cell, ParsedWorkbook, ParseOptions, SheetInfo
from .modules.styles.parser import parse_styles
from .modules.workbook.metadata import _parse_workbook_xml
from .modules.workbook.shared_strings import _parse_shared_strings
from .modules.worksheets.comments import parse_threaded_comment_people
from .modules.worksheets.post import parse_tables
from .modules.worksheets.scanner import parse_sheet
from .modules.worksheets.sheet_types import SheetParseResult
from .plan import XlsxParsePlan


class OperationSource:
    def __init__(self, source: Source, options: ParseOptions | None = None) -> None:
        selected = options or ParseOptions()
        self.options = selected
        self.package = PackageReader(
            source,
            PackageLimits(selected.max_zip_entries, selected.max_entry_uncompressed_bytes, selected.max_total_uncompressed_bytes),
        )
        self._stack = ExitStack()
        self.warnings: list[ParseWarning] = []
        self._relationships: dict[str, list[RelationshipRecord]] = {}
        self._people: dict[str, str] | None = None
        self._started = perf_counter()

    def __enter__(self) -> OperationSource:
        try:
            self._stack.enter_context(self.package)
            self.package.validate("xl/workbook.xml")
            date_1904, self.sheets, self.names, self.links = _parse_workbook_xml(
                self.package, include_defined_names=False, include_external_links=False
            )
            self.strings, self.rich = _parse_shared_strings(self.package, self.warnings, include_rich_text=False)
            self.formats = parse_styles(self.package, detail="display", locale=self.options.locale)
            self.formats.set_date_system(date_1904)
        except BaseException:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._stack.close()

    def relationships(self, sheet: SheetInfo) -> list[RelationshipRecord]:
        part = sheet["part"]
        if part not in self._relationships:
            try:
                self._relationships[part] = list(self.package.read_relationships_for_part(part))
            except (ET.ParseError, KeyError, ValueError) as exc:
                self.warnings.append(ParseWarning("SHEET_RELS_INVALID", f"Invalid worksheet relationships: {exc}", part))
                self._relationships[part] = []
        return self._relationships[part]

    def tables(self) -> None:
        index = 0
        for sheet in self.sheets:
            if sheet.get("kind") != "chartsheet":
                tables = parse_tables(self.relationships(sheet), self.package, start_index=index, warnings=self.warnings)
                sheet["tables"] = tables
                index += len(tables)

    def scan(
        self, sheet: SheetInfo, plan: XlsxParsePlan, *, row_sink: Callable[[int, list[Cell]], bool] | None = None
    ) -> SheetParseResult:
        from .plan import XlsxFeature

        if plan.needs(XlsxFeature.COMMENTS) and self._people is None:
            self._people = parse_threaded_comment_people(self.package, self.warnings)
        if sheet.get("kind") == "chartsheet":
            return SheetParseResult([], [], False, "", [], [], [], [], [])
        result = parse_sheet(
            self.package,
            sheet["part"],
            self.strings,
            self.rich,
            self.formats,
            self.relationships(sheet),
            self._people,
            plan=plan,
            cell_window=plan.cell_window,
            row_sink=row_sink,
        )
        for warning in result.warnings:
            if warning not in self.warnings:
                self.warnings.append(warning)
        return result

    def preflight(
        self, sheet: SheetInfo, bounds: tuple[int, int, int, int], header: int | None, *, annotations: bool = True
    ) -> SheetParseResult:
        _left, top, _right, bottom = bounds
        row = header if header is not None and top <= header <= bottom else 0
        plan = XlsxParsePlan.values(sheet["name"], window=(1, row, 16_384, row), annotations=annotations)
        return self.scan(sheet, plan)

    def workbook(self) -> ParsedWorkbook:
        return {
            "sheets": self.sheets,
            "fmt_index": self.formats,
            "metadata": {
                "source": "<operation>",
                "defined_names": self.names,
                "external_links": self.links,
                "pivot_caches": [],
                "slicers": [],
                "timelines": [],
            },
            "report": ParseReport(
                "xlsx",
                1,
                {"sheetCount": len(self.sheets)},
                tuple(self.warnings),
                {"stagesMs": {"parse": (perf_counter() - self._started) * 1000}, "counters": {}},
            ),
        }

    def result(self, text: str, kind: str) -> ParseResult:
        return ParseResult(
            text=text,
            density="structural",
            selection={"kind": kind},
            report=self.workbook()["report"],
            syntax_version="doctokens-xml/1.0",
            media_type="application/xml",
        )
