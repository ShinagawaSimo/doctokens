"""Public XLSX parsing and explicit read-session API."""

from __future__ import annotations

from collections.abc import Iterator

from ooxml_llm_core.doctokens_xml import element
from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor
from ooxml_llm_core.package import PackageReader
from ooxml_llm_core.resource_xml import resource_document
from ooxml_llm_core.session import SessionLifecycle
from ooxml_llm_core.text_search import TextSearchOptions, TextSearchResult, search_text

from ._api_support import Source, _density, _result
from ._reading import render_selection
from ._resources import _render_chart_resource, _resource_descriptors
from .models import ParsedWorkbook, ParseOptions
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan
from .query import AggregateSpec, OrderSpec, WhereCondition
from .query import query_data as _query_data
from .rendering.selection import parse_range
from .search import _find_cells
from .text_search import text_units


class XlsxReadSession:
    """Context-managed XLSX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions, *, memory_limit_bytes: int | None = None) -> None:
        self.source = source
        self.options = options
        self._memory_limit_bytes = memory_limit_bytes
        self.parsed_workbook: ParsedWorkbook | None = None
        self._package: PackageReader | None = None
        self._lifecycle: SessionLifecycle[ParsedWorkbook] = SessionLifecycle("XLSX")

    def __enter__(self) -> XlsxReadSession:
        self._lifecycle.check_new()
        limits = PackageLimits(
            max_zip_entries=self.options.max_zip_entries,
            max_entry_uncompressed_bytes=self.options.max_entry_uncompressed_bytes,
            max_total_uncompressed_bytes=self.options.max_total_uncompressed_bytes,
        )
        self._package = PackageReader(self.source, limits, memory_limit_bytes=self._memory_limit_bytes)
        package = self._package
        try:
            self.parsed_workbook = self._lifecycle.enter(
                package, lambda: _parse_workbook(package, self.options, plan=XlsxParsePlan.session())
            )
            package.clear_part_cache()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._lifecycle.close()
        self._package = None
        self.parsed_workbook = None

    def _require_open(self) -> ParsedWorkbook:
        return self._lifecycle.require()

    @property
    def estimated_memory_bytes(self) -> int:
        self._require_open()
        budget = self._package.memory_budget if self._package is not None else None
        return budget.estimated_bytes if budget is not None else 0

    @property
    def report(self) -> ParseReport:
        return self._require_open()["report"]

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

    def describe(self) -> dict[str, object]:
        return {
            "format": "xlsx",
            "report": self.report.to_dict(),
            "sheets": [
                {
                    "name": s["name"],
                    "kind": s.get("kind", "worksheet"),
                    "visibility": s.get("state", "visible"),
                    "tables": s.get("tables", []),
                }
                for s in self._require_open()["sheets"]
            ],
        }

    def render(
        self,
        *,
        density: str = "structural",
        sheet: str | None = None,
        range_spec: str | None = None,
    ) -> ParseResult:
        workbook = self._require_open()
        resolved = _density(density)
        return render_selection(workbook, resolved, sheet, range_spec)

    def iter_render(
        self,
        *,
        density: str = "structural",
        sheet: str | None = None,
        range_spec: str | None = None,
    ) -> Iterator[str]:
        chunks = iter((self.render(density=density, sheet=sheet, range_spec=range_spec).text,))

        def guarded() -> Iterator[str]:
            for chunk in chunks:
                self._require_open()
                yield chunk

        return guarded()

    def find_text(
        self, query: str, *, options: TextSearchOptions | None = None, sheets: list[str] | None = None
    ) -> TextSearchResult:
        return search_text(text_units(self._require_open(), sheets), query, options or TextSearchOptions())

    def find_cells(
        self,
        query: str,
        *,
        sheets: list[str] | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> ParseResult:
        workbook = self._require_open()
        text = _find_cells(workbook, query, sheets=sheets, kind=kind, limit=limit)
        return _result(
            workbook,
            text,
            "structural",
            {"kind": "search"},
            syntax_version="doctokens-xml/1.0",
            media_type="application/xml",
        )

    def query_data(
        self,
        *,
        table_id: str | None = None,
        sheet: str | None = None,
        range_spec: str | None = None,
        header_row: int | None = None,
        select: list[str] | None = None,
        where: list[WhereCondition] | None = None,
        group_by: list[str] | None = None,
        aggregates: list[AggregateSpec] | None = None,
        order_by: list[OrderSpec] | None = None,
        limit: int | None = None,
    ) -> ParseResult:
        workbook = self._require_open()
        text = _query_data(
            workbook,
            table_id=table_id,
            sheet=sheet,
            range_spec=range_spec,
            header_row=header_row,
            select=select,
            where=where,
            group_by=group_by,
            aggregates=aggregates,
            order_by=order_by,
            limit=limit,
        )
        return _result(
            workbook,
            text,
            "structural",
            {"kind": "query"},
            syntax_version="doctokens-xml/1.0",
            media_type="application/xml",
        )

    def read_resource(self, kind: str, resource_id: str) -> bytes:
        workbook = self._require_open()
        if kind != "image":
            raise ValueError("XLSX binary resources currently support only 'image'")
        descriptor = next(
            (item for item in _resource_descriptors(workbook) if item.kind == kind and item.id == resource_id),
            None,
        )
        if descriptor is None:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        if descriptor.part is None or self._package is None:
            raise ValueError(f"resource {kind!r}/{resource_id!r} has no readable package part")
        return self._package.read_part(descriptor.part)

    def render_resource(self, kind: str, resource_id: str) -> ParseResult:
        workbook = self._require_open()
        if kind == "chart":
            for sheet in workbook["sheets"]:
                for chart in sheet.get("charts", []):
                    if chart["id"] == resource_id:
                        return _result(
                            workbook,
                            _render_chart_resource(chart),
                            "semantic",
                            _resource_selection(kind, resource_id),
                            syntax_version="doctokens-xml/1.0",
                            media_type="application/xml",
                        )
        if kind == "pivot_table":
            for sheet in workbook["sheets"]:
                for pivot in sheet.get("pivot_tables", []):
                    if pivot["id"] == resource_id:
                        text = resource_document("xlsx", element("pivot-table", id=resource_id, name=pivot.get("name", "")))
                        return _result(
                            workbook,
                            text,
                            "semantic",
                            _resource_selection(kind, resource_id),
                            syntax_version="doctokens-xml/1.0",
                            media_type="application/xml",
                        )
        raise KeyError(f"resource {kind!r}/{resource_id!r} not found")


def _resource_selection(kind: str, resource_id: str) -> dict[str, object]:
    return {"kind": "resource", "resource_kind": kind, "id": resource_id}


def open_xlsx(source: Source, *, options: ParseOptions | None = None, memory_limit_bytes: int | None = None) -> XlsxReadSession:
    return XlsxReadSession(source, options or ParseOptions(), memory_limit_bytes=memory_limit_bytes)


def parse_xlsx(
    source: Source,
    *,
    density: str = "structural",
    sheet: str | None = None,
    range_spec: str | None = None,
    options: ParseOptions | None = None,
) -> ParseResult:
    resolved = _density(density)
    if range_spec is not None and sheet is None:
        raise ValueError("range_spec requires sheet")
    if sheet is None:
        plan = XlsxParsePlan.render(resolved)
    elif range_spec is None:
        plan = XlsxParsePlan.sheet(resolved, sheet)
    else:
        start_col, start_row, end_col, end_row = parse_range(range_spec)
        plan = XlsxParsePlan.range(resolved, sheet, (start_col, start_row, end_col, end_row))
    workbook = _parse_workbook(source, options or ParseOptions(), plan=plan)
    return render_selection(workbook, resolved, sheet, range_spec)


__all__ = ["XlsxReadSession", "open_xlsx", "parse_xlsx"]
