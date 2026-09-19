"""Public XLSX parsing and explicit read-session API."""

from __future__ import annotations

import re
from collections.abc import Iterator
from html import escape as escape_text
from pathlib import Path

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor
from ooxml_llm_core.package import PackageReader

from .models import Cell, DrawingChart, ParsedWorkbook, ParseOptions, SheetInfo
from .parsing import get_render_pipeline
from .parsing.runner import _parse_workbook
from .plan import XlsxParsePlan
from .query import AggregateSpec, OrderSpec, WhereCondition
from .query import query_data as _query_data
from .rendering.structural import _filter_rows, _find_sheet, _parse_range, _render_grid

Source = str | Path | bytes
_DENSITIES = {"plain", "structural", "semantic"}


def _density(value: str) -> str:
    if value not in _DENSITIES:
        raise ValueError(f"density must be one of: {', '.join(sorted(_DENSITIES))}")
    return value


def _resource_descriptors(workbook: ParsedWorkbook) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for sheet in workbook["sheets"]:
        descriptors.extend(
            ResourceDescriptor(
                id=image["id"],
                kind="image",
                source="embedded",
                locator=f"{sheet['name']}!{image.get('ref', '')}",
                part=image.get("part"),
            )
            for image in sheet.get("images", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=chart["id"],
                kind="chart",
                source="embedded",
                locator=f"{sheet['name']}!{chart.get('ref', '')}",
                part=chart.get("part"),
            )
            for chart in sheet.get("charts", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=pivot["id"],
                kind="pivot_table",
                source="embedded",
                locator=f"{sheet['name']}!{pivot.get('ref', '')}",
            )
            for pivot in sheet.get("pivot_tables", [])
        )
        descriptors.extend(
            ResourceDescriptor(
                id=table["id"],
                kind="table",
                source="embedded",
                locator=f"{sheet['name']}!{table.get('ref', '')}",
            )
            for table in sheet.get("tables", [])
        )
    return tuple(descriptors)


def _result(workbook: ParsedWorkbook, text: str, density: str, selection: dict[str, object]) -> ParseResult:
    return ParseResult(text, density, selection, workbook["report"], _resource_descriptors(workbook))  # type: ignore[arg-type]


def _sheet(workbook: ParsedWorkbook, name: str) -> SheetInfo:
    try:
        return _find_sheet(workbook, name)
    except ValueError as exc:
        raise KeyError(name) from exc


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
            text = _render_grid(sheet_info.get("rows", []), resolved, workbook, cell_budget=None)
            selection = {"kind": "sheet", "sheet": sheet}
        else:
            sheet_info = _sheet(workbook, sheet)
            start_col, start_row, end_col, end_row = _parse_range(range_spec)
            rows = _filter_rows(sheet_info.get("rows", []), start_col, start_row, end_col, end_row)
            text = _render_grid(rows, resolved, workbook, cell_budget=None)
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
        return _result(workbook, text, "structural", {"kind": "search"})

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
        return _result(workbook, text, "structural", {"kind": "query"})

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
                        )
        if kind == "pivot_table":
            for sheet in workbook["sheets"]:
                for pivot in sheet.get("pivot_tables", []):
                    if pivot["id"] == resource_id:
                        text = f"<pivotTable id={resource_id} name={pivot.get('name', '')}/>"
                        return _result(workbook, text, "semantic", _resource_selection(kind, resource_id))
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
        start_col, start_row, end_col, end_row = _parse_range(range_spec)
        plan = XlsxParsePlan.range(resolved, sheet, (start_col, start_row, end_col, end_row))
    workbook = _parse_workbook(source, options or ParseOptions(), plan=plan)
    if sheet is None:
        text = "".join(get_render_pipeline(resolved).render(workbook))
        selection: dict[str, object] = {"kind": "all"}
    elif range_spec is None:
        sheet_info = _sheet(workbook, sheet)
        text = _render_grid(sheet_info.get("rows", []), resolved, workbook, cell_budget=None)
        selection = {"kind": "sheet", "sheet": sheet}
    else:
        sheet_info = _sheet(workbook, sheet)
        text = _render_grid(sheet_info.get("rows", []), resolved, workbook, cell_budget=None)
        selection = {"kind": "range", "sheet": sheet, "ref": range_spec}
    return _result(workbook, text, resolved, selection)


def _find_cells(
    workbook: ParsedWorkbook,
    query: str,
    *,
    sheets: list[str] | None,
    kind: str | None,
    limit: int,
) -> str:
    if not query:
        return "<matches>\n"
    pattern = re.compile(re.escape(query))
    matches: list[str] = []
    selected_sheets = sheets or [sheet["name"] for sheet in workbook["sheets"]]
    seen_names: set[str] = set()
    for sheet_name in selected_sheets:
        if len(matches) >= limit:
            break
        sheet = _sheet(workbook, sheet_name)
        for row in sheet.get("rows", []):
            for cell in row:
                if len(matches) >= limit:
                    break
                match = _cell_match(sheet_name, cell, pattern, kind)
                if match is not None:
                    matches.append(match)
        if len(matches) < limit and kind in {None, "definedName"}:
            for defined_name in workbook["metadata"].get("defined_names", []):
                if len(matches) >= limit:
                    break
                name = defined_name["name"]
                if name in seen_names:
                    continue
                scope = defined_name.get("scopeSheet")
                if scope and scope != sheet_name:
                    continue
                if pattern.search(name) or pattern.search(defined_name.get("ref", "")):
                    seen_names.add(name)
                    matches.append(f"<match field=definedName>{escape_text(name)} = {escape_text(defined_name['ref'])}")
    return "<matches>\n" + "\n".join(matches) + "\n"


def _cell_match(sheet_name: str, cell: Cell, pattern: re.Pattern[str], kind: str | None) -> str | None:
    fields = (
        ("value", cell["text"]),
        ("formula", cell.get("formula", "")),
        ("comment", cell.get("comment", "")),
        ("hyperlink", cell.get("hyperlink", "")),
    )
    for field_name, value in fields:
        if kind not in {None, field_name}:
            continue
        rendered = str(value)
        if pattern.search(rendered):
            cell_ref = f"{escape_text(sheet_name, quote=True)}!{cell['ref']}"
            return f'<match cell="{cell_ref}" field={field_name}>{escape_text(rendered)}'
    return None


def _render_chart_resource(chart: DrawingChart) -> str:
    attrs = f"id={chart['id']} ref={chart['ref']} type={chart.get('type', '?')}"
    if chart.get("plotTypes"):
        attrs += f" plots={escape_text(','.join(chart['plotTypes']), quote=True)}"
    attrs += f" series={chart.get('series_count', 0)}"
    if chart.get("title"):
        attrs += f" title={escape_text(chart['title'], quote=True)}"
    parts = [f"<chart {attrs}>"]
    is_combination = chart.get("type") == "combination"
    for series in chart.get("series", []):
        series_attrs = f"index={series.get('index', 0)}"
        if series.get("name"):
            series_attrs += f" name={escape_text(series['name'], quote=True)}"
        if "min" in series:
            series_attrs += f" min={series['min']}"
        if "max" in series:
            series_attrs += f" max={series['max']}"
        if is_combination and series.get("chartType"):
            series_attrs += f" type={series['chartType']}"
        if series.get("bubbleSizes"):
            series_attrs += f" bubbleSizes={escape_text(','.join(series['bubbleSizes']), quote=True)}"
        if series.get("hidden"):
            series_attrs += " hidden"
        parts.append(f"\n<series {series_attrs}>")
        for point in series.get("points", []):
            point_attrs = ""
            for name in ("category", "value", "x", "y", "bubbleSize"):
                value = point.get(name, "")
                if value:
                    point_attrs += f" {name}={escape_text(str(value), quote=True)}"
            parts.append(f"\n<point{point_attrs}/>")
    return "".join(parts)


__all__ = ["XlsxReadSession", "open_xlsx", "parse_xlsx"]
