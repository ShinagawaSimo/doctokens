"""Public XLSX parsing and explicit read-session API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

from ooxml_llm_core.doctokens_plain import render_plain
from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import Density, ParseReport, ParseResult, ResourceDescriptor
from ooxml_llm_core.package import PackageReader

from ._resources import _render_chart_resource, _resource_descriptors
from .models import Cell, ParsedWorkbook, ParseOptions, SheetInfo
from .parsing import get_render_pipeline
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan
from .query import AggregateSpec, OrderSpec, WhereCondition
from .query import query_data as _query_data
from .rendering.dtx import render_sheet_dtx
from .rendering.plain import iter_plain_rows
from .rendering.selection import filter_rows, parse_range
from .search import _find_cells, _sheet

Source = str | Path | bytes
_DENSITIES = {"plain", "structural", "semantic"}


def _density(value: str) -> str:
    if value not in _DENSITIES:
        raise ValueError(f"density must be one of: {', '.join(sorted(_DENSITIES))}")
    return value


def _result(
    workbook: ParsedWorkbook,
    text: str,
    density: str,
    selection: dict[str, object],
    *,
    syntax_version: str | None = None,
    media_type: str | None = None,
) -> ParseResult:
    resolved_syntax, resolved_media_type = _output_metadata(density)
    return ParseResult(
        text,
        cast(Density, density),
        selection,
        workbook["report"],
        _resource_descriptors(workbook),
        syntax_version or resolved_syntax,
        media_type or resolved_media_type,
    )


def _output_metadata(density: str) -> tuple[str, str]:
    if density == "plain":
        return "doctokens-plain/1.0", "text/plain"
    return "doctokens-xml/1.0", "application/xml"


class XlsxReadSession:
    """Context-managed XLSX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed_workbook: ParsedWorkbook | None = None
        self._package: PackageReader | None = None
        self._state = "new"

    def __enter__(self) -> XlsxReadSession:
        if self._state != "new":
            raise RuntimeError("XLSX session cannot be entered twice")
        limits = PackageLimits(
            max_zip_entries=self.options.max_zip_entries,
            max_entry_uncompressed_bytes=self.options.max_entry_uncompressed_bytes,
            max_total_uncompressed_bytes=self.options.max_total_uncompressed_bytes,
        )
        self._package = PackageReader(self.source, limits)
        try:
            self._package.__enter__()
            self.parsed_workbook = _parse_workbook(self._package, self.options, plan=XlsxParsePlan.session())
        except BaseException:
            self.close()
            raise
        self._state = "open"
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._state == "closed":
            return
        if self._package is not None:
            self._package.__exit__(None, None, None)
            self._package = None
        self.parsed_workbook = None
        self._state = "closed"

    def _require_open(self) -> ParsedWorkbook:
        if self._state != "open" or self.parsed_workbook is None:
            raise RuntimeError("XLSX session is not open")
        return self.parsed_workbook

    @property
    def report(self) -> ParseReport:
        return self._require_open()["report"]

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

    def render(
        self,
        *,
        density: str = "structural",
        sheet: str | None = None,
        range_spec: str | None = None,
    ) -> ParseResult:
        workbook = self._require_open()
        resolved = _density(density)
        if range_spec is not None and sheet is None:
            raise ValueError("range_spec requires sheet")
        if sheet is None:
            text = "".join(get_render_pipeline(resolved).render(workbook))
            selection: dict[str, object] = {"kind": "all"}
        elif range_spec is None:
            sheet_info = _sheet(workbook, sheet)
            text = _render_selected_plain(sheet_info) if resolved == "plain" else render_sheet_dtx(workbook, sheet_info, resolved)
            selection = {"kind": "sheet", "sheet": sheet}
        else:
            sheet_info = _sheet(workbook, sheet)
            start_col, start_row, end_col, end_row = parse_range(range_spec)
            rows = filter_rows(sheet_info.get("rows", []), start_col, start_row, end_col, end_row)
            text = (
                _render_selected_plain(sheet_info, rows)
                if resolved == "plain"
                else render_sheet_dtx(
                    workbook,
                    sheet_info,
                    resolved,
                    rows,
                )
            )
            selection = {"kind": "range", "sheet": sheet, "ref": range_spec}
        return _result(workbook, text, resolved, selection)

    def iter_render(
        self,
        *,
        density: str = "structural",
        sheet: str | None = None,
        range_spec: str | None = None,
    ) -> Iterator[str]:
        workbook = self._require_open()
        resolved = _density(density)
        if range_spec is not None and sheet is None:
            raise ValueError("range_spec requires sheet")
        if sheet is None:
            chunks = get_render_pipeline(resolved).render(workbook)
        else:
            chunks = iter((self.render(density=resolved, sheet=sheet, range_spec=range_spec).text,))

        def guarded() -> Iterator[str]:
            for chunk in chunks:
                self._require_open()
                yield chunk

        return guarded()

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
            syntax_version="legacy-markup/0",
            media_type="text/plain",
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
            syntax_version="legacy-markup/0",
            media_type="text/plain",
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
                            syntax_version="legacy-markup/0",
                            media_type="text/plain",
                        )
        if kind == "pivot_table":
            for sheet in workbook["sheets"]:
                for pivot in sheet.get("pivot_tables", []):
                    if pivot["id"] == resource_id:
                        text = f"<pivotTable id={resource_id} name={pivot.get('name', '')}/>"
                        return _result(
                            workbook,
                            text,
                            "semantic",
                            _resource_selection(kind, resource_id),
                            syntax_version="legacy-markup/0",
                            media_type="text/plain",
                        )
        raise KeyError(f"resource {kind!r}/{resource_id!r} not found")


def _resource_selection(kind: str, resource_id: str) -> dict[str, object]:
    return {"kind": "resource", "resource_kind": kind, "id": resource_id}


def open_xlsx(source: Source, *, options: ParseOptions | None = None) -> XlsxReadSession:
    return XlsxReadSession(source, options or ParseOptions())


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
    if sheet is None:
        text = "".join(get_render_pipeline(resolved).render(workbook))
        selection: dict[str, object] = {"kind": "all"}
    elif range_spec is None:
        sheet_info = _sheet(workbook, sheet)
        text = _render_selected_plain(sheet_info) if resolved == "plain" else render_sheet_dtx(workbook, sheet_info, resolved)
        selection = {"kind": "sheet", "sheet": sheet}
    else:
        sheet_info = _sheet(workbook, sheet)
        start_col, start_row, end_col, end_row = parse_range(range_spec)
        rows = filter_rows(sheet_info.get("rows", []), start_col, start_row, end_col, end_row)
        if resolved == "plain":
            text = _render_selected_plain(sheet_info, rows)
        else:
            text = render_sheet_dtx(workbook, sheet_info, resolved, rows)
        selection = {"kind": "range", "sheet": sheet, "ref": range_spec}
    return _result(workbook, text, resolved, selection)


def _render_selected_plain(sheet: SheetInfo, rows: list[list[Cell]] | None = None) -> str:
    selected = sheet.get("rows", []) if rows is None else rows
    return render_plain(
        "density=plain\n" + "".join(iter_plain_rows(selected, hidden_cols=sheet.get("hidden_cols", []))),
        format_name="xlsx",
    )


__all__ = ["XlsxReadSession", "open_xlsx", "parse_xlsx"]
