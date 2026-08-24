"""Public API — accepts source files directly, returns rendered results."""

from __future__ import annotations

import re
from collections.abc import Iterator
from html import escape
from pathlib import Path

from ooxml_llm_core.models import ParseReport

from .models import Cell, DefinedName, DrawingChart, ParsedWorkbook, ParseOptions, SheetInfo
from .parser import _parse_workbook
from .query import AggregateSpec, OrderSpec, WhereCondition
from .query import query_data as _query_data
from .renderers.structural import (
    _filter_rows,
    _find_sheet,
    _parse_range,
    _render_grid,
    _render_sheet,
)

_VALID_DENSITIES = {"plain", "structural", "semantic"}


class LoadedWorkbook:
    """Explicitly loaded XLSX facade for repeated downstream operations."""

    def __init__(self, workbook: ParsedWorkbook, options: ParseOptions) -> None:
        self.workbook = workbook
        self.options = options

    @property
    def report(self) -> ParseReport:
        return self.workbook["report"]

    def render(self, *, density: str = "structural", start_row: int = 1) -> str:
        _validate_density(density)
        return "".join(self.iter_render(density=density, start_row=start_row))

    def iter_render(self, *, density: str = "structural", start_row: int = 1) -> Iterator[str]:
        _validate_density(density)
        return _iter_rendered_workbook(self.workbook, density, start_row)

    def render_range(self, sheet: str, range_spec: str, *, density: str = "structural") -> str:
        _validate_density(density)
        sheet_info = _find_sheet(self.workbook, sheet)
        start_col, start_row, end_col, end_row = _parse_range(range_spec)
        filtered = _filter_rows(sheet_info.get("rows", []), start_col, start_row, end_col, end_row)
        return _render_grid(filtered, density, self.workbook, cell_budget=None)

    def find_cells(
        self,
        query: str,
        *,
        sheets: list[str] | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> str:
        return _find_cells_in_workbook(self.workbook, query, sheets=sheets, kind=kind, limit=limit)

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
    ) -> str:
        return _query_data(
            self.workbook,
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

    def get_resource(self, resource_type: str, resource_id: str) -> str | None:
        return _get_resource_from_workbook(self.workbook, resource_type, resource_id)


def _validate_density(density: str) -> None:
    if density not in _VALID_DENSITIES:
        raise ValueError(f"Invalid density {density!r}; expected one of {sorted(_VALID_DENSITIES)}")


def parse_xlsx(
    source: str | Path | bytes,
    *,
    density: str = "structural",
    start_row: int = 1,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse *source* and render the entire workbook at the given density.

    Returns a string by default.  Set *stream=True* to receive an iterator
    of rendered output chunks. Parsing itself is still completed before the
    iterator is returned.

    *start_row* (1-based) begins rendering from the specified row for the
    first data sheet, enabling paginated window reads of large grids.
    """
    _validate_density(density)
    loaded = load_xlsx(source, options=options)
    if stream:
        return loaded.iter_render(density=density, start_row=start_row)
    return loaded.render(density=density, start_row=start_row)


def iter_workbook(
    source: str | Path | bytes,
    *,
    density: str = "structural",
    start_row: int = 1,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Parse *source* and yield rendered output chunks after parsing completes."""
    return load_xlsx(source, options=options).iter_render(density=density, start_row=start_row)


def load_xlsx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> LoadedWorkbook:
    """Parse once and return an explicit reusable workbook facade."""
    opts = options or ParseOptions()
    return LoadedWorkbook(_parse_workbook(source, opts), opts)


def _iter_rendered_workbook(wb: ParsedWorkbook, density: str, start_row: int) -> Iterator[str]:
    """Yield rendered chunks for a parsed workbook."""
    yield f"density={density}\n"
    for sheet_index, sheet in enumerate(wb["sheets"]):
        yield from _render_sheet(sheet, density, wb, start_row=start_row, emit_globals=sheet_index == 0)
        if sheet.get("kind") != "chartsheet" and start_row != 1:
            start_row = 1


def render_range(
    source: str | Path | bytes,
    sheet: str,
    range_spec: str,
    *,
    density: str = "structural",
    options: ParseOptions | None = None,
) -> str:
    """Render cells within an A1-style range from *source*.

    Range reads are exact: the default-view cell budget never truncates them.
    """
    return load_xlsx(source, options=options).render_range(sheet, range_spec, density=density)


def find_cells(
    source: str | Path | bytes,
    query: str,
    *,
    sheets: list[str] | None = None,
    kind: str | None = None,
    limit: int = 50,
    options: ParseOptions | None = None,
) -> str:
    """Search values, formulas, comments, hyperlinks, and defined names across sheets.

    *kind* narrows to one of ``value``, ``formula``, ``comment``, ``hyperlink``,
    ``definedName``.
    """
    return _find_cells_in_workbook(load_xlsx(source, options=options).workbook, query, sheets=sheets, kind=kind, limit=limit)


def _find_cells_in_workbook(
    wb: ParsedWorkbook,
    query: str,
    *,
    sheets: list[str] | None,
    kind: str | None,
    limit: int,
) -> str:
    if not query:
        return "<matches>\n"
    pattern = re.compile(re.escape(query))  # exact match by default
    matches: list[str] = []
    sheets_to_search = sheets or [s["name"] for s in wb["sheets"]]
    seen_names: set[str] = set()

    for sheet_name in sheets_to_search:
        if len(matches) >= limit:
            break
        sheet_info = _find_sheet(wb, sheet_name)
        remaining = limit - len(matches)
        matches.extend(_find_cell_matches(sheet_info, sheet_name, pattern, kind, remaining))
        if len(matches) < limit and kind in {None, "definedName"}:
            remaining = limit - len(matches)
            defined_names = wb["metadata"].get("defined_names", [])
            matches.extend(_find_defined_name_matches(defined_names, sheet_name, pattern, remaining, seen_names))

    parts = ["<matches>\n"]
    parts.append("\n".join(matches[:limit]))
    return "".join(parts) + "\n"


def _find_cell_matches(
    sheet: SheetInfo,
    sheet_name: str,
    pattern: re.Pattern[str],
    kind: str | None,
    limit: int,
) -> list[str]:
    matches: list[str] = []
    for row_cells in sheet.get("rows", []):
        for cell in row_cells:
            if len(matches) >= limit:
                return matches
            match = _cell_match(sheet_name, cell, pattern, kind)
            if match is not None:
                matches.append(match)
    return matches


def _cell_match(sheet_name: str, cell: Cell, pattern: re.Pattern[str], kind: str | None) -> str | None:
    cell_ref = f"{escape(sheet_name, quote=True)}!{cell['ref']}"
    fields = (
        ("value", cell["text"]),
        ("formula", cell.get("formula", "")),
        ("comment", cell.get("comment", "")),
        ("hyperlink", cell.get("hyperlink", "")),
    )
    for field_name, raw_value in fields:
        if kind not in {None, field_name}:
            continue
        value = str(raw_value)
        if pattern.search(value):
            return f'<match cell="{cell_ref}" field={field_name}>{escape(value)}'
    return None


def _find_defined_name_matches(
    defined_names: list[DefinedName],
    sheet_name: str,
    pattern: re.Pattern[str],
    limit: int,
    seen_names: set[str],
) -> list[str]:
    matches: list[str] = []
    for defined_name in defined_names:
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
            escaped_name = escape(name)
            ref = escape(defined_name["ref"])
            matches.append(f"<match field=definedName>{escaped_name} = {ref}")
    return matches


def query_data(
    source: str | Path | bytes,
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
    options: ParseOptions | None = None,
) -> str:
    """Query a declared Table or explicit range with projection, filtering,
    grouping, and aggregation.  Returns lightweight tabular HTML.
    """
    wb = load_xlsx(source, options=options).workbook
    return _query_data(
        wb,
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


def get_resource(
    source: str | Path | bytes,
    resource_type: str,
    resource_id: str,
    *,
    options: ParseOptions | None = None,
) -> str | None:
    """Return a resource by type and ID as an HTML string for LLM consumption.

    *resource_type*: ``image``, ``chart``, ``pivot_table``, ``embedded_object``.
    """
    return _get_resource_from_workbook(load_xlsx(source, options=options).workbook, resource_type, resource_id)


def _get_resource_from_workbook(wb: ParsedWorkbook, resource_type: str, resource_id: str) -> str | None:

    if resource_type == "image":
        for sheet_info in wb["sheets"]:
            for image in sheet_info.get("images", []):
                if image["id"] == resource_id:
                    return f"<image id={resource_id} ref={image['ref']}/>"
    elif resource_type == "chart":
        for sheet_info in wb["sheets"]:
            for chart in sheet_info.get("charts", []):
                if chart["id"] == resource_id:
                    return _render_chart_resource(chart)
    elif resource_type == "pivot_table":
        for sheet_info in wb["sheets"]:
            for pivot_table in sheet_info.get("pivot_tables", []):
                if pivot_table["id"] == resource_id:
                    return f"<pivotTable id={resource_id} name={pivot_table.get('name', '')}/>"
    return None


def _render_chart_resource(chart: DrawingChart) -> str:
    """Render a chart as an HTML string — full series data."""
    from html import escape

    attrs = f"id={chart['id']} ref={chart['ref']} type={chart.get('type', '?')}"
    if chart.get("plotTypes"):
        attrs += f" plots={escape(','.join(chart['plotTypes']), quote=True)}"
    attrs += f" series={chart.get('series_count', 0)}"
    if chart.get("title"):
        attrs += f" title={escape(chart['title'], quote=True)}"
    parts = [f"<chart {attrs}>"]
    is_combination = chart.get("type") == "combination"

    for series in chart.get("series", []):
        series_attrs = f"index={series.get('index', 0)}"
        if series.get("name"):
            series_attrs += f" name={escape(series['name'], quote=True)}"
        if "min" in series:
            series_attrs += f" min={series['min']}"
        if "max" in series:
            series_attrs += f" max={series['max']}"
        if is_combination and series.get("chartType"):
            series_attrs += f" type={series['chartType']}"
        if series.get("bubbleSizes"):
            series_attrs += f" bubbleSizes={escape(','.join(series['bubbleSizes']), quote=True)}"
        if series.get("hidden"):
            series_attrs += " hidden"
        parts.append(f"\n<series {series_attrs}>")
        for point in series.get("points", []):
            point_attrs = ""
            category = point.get("category", "")
            value = point.get("value", "")
            if category:
                point_attrs += f" category={escape(category, quote=True)}"
            if value:
                point_attrs += f" value={escape(value, quote=True)}"
            if point.get("x"):
                point_attrs += f" x={escape(point['x'], quote=True)}"
            if point.get("y"):
                point_attrs += f" y={escape(point['y'], quote=True)}"
            if point.get("bubbleSize"):
                point_attrs += f" bubbleSize={escape(point['bubbleSize'], quote=True)}"
            parts.append(f"\n<point{point_attrs}/>")

    return "".join(parts)
