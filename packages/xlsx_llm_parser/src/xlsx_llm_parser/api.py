"""Public XLSX API for parsing, rendering, searching, and querying."""

from __future__ import annotations

import re
from collections.abc import Iterator
from html import escape as escape_text
from pathlib import Path

from ooxml_llm_core.models import ParseReport

from .models import Cell, DefinedName, DrawingChart, ParsedWorkbook, ParseOptions, SheetInfo
from .parser import _parse_workbook
from .plan import XlsxParsePlan
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
    """Reusable, already-parsed XLSX workbook facade.

    The workbook is parsed once by :func:`load_xlsx`.  This facade then serves
    repeated output rendering, range reads, searches, queries, and resource
    reads from the same in-memory representation.
    """

    def __init__(self, parsed_workbook: ParsedWorkbook, parse_options: ParseOptions) -> None:
        self.parsed_workbook = parsed_workbook
        self.parse_options = parse_options

    @property
    def report(self) -> ParseReport:
        """Return diagnostics collected while parsing this workbook."""
        return self.parsed_workbook["report"]

    def render(self, *, density: str = "structural", start_row: int = 1) -> str:
        """Render the complete loaded workbook.

        Args:
            density: ``plain`` for values only, ``structural`` for workbook
                structure, or ``semantic`` for structure and formatting.
            start_row: One-based row at which rendering starts on the first
                data sheet; later sheets start at row one.

        Returns:
            The complete self-defined LLM output string.
        """
        _validate_density(density)
        return "".join(self.iter_render(density=density, start_row=start_row))

    def iter_render(self, *, density: str = "structural", start_row: int = 1) -> Iterator[str]:
        """Yield loaded-workbook output chunks at the requested density.

        Args:
            density: Output detail level: ``plain``, ``structural``, or
                ``semantic``.
            start_row: One-based starting row for the first data sheet.

        Returns:
            An iterator whose chunks concatenate to the value of :meth:`render`.
        """
        _validate_density(density)
        return _iter_rendered_workbook(self.parsed_workbook, density, start_row)

    def render_range(self, sheet: str, range_spec: str, *, density: str = "structural") -> str:
        """Render an exact A1-style range from one loaded worksheet.

        Args:
            sheet: Worksheet name.
            range_spec: A1-style range such as ``A1:C20``.
            density: Output detail level: ``plain``, ``structural``, or
                ``semantic``.

        Returns:
            Output for exactly the requested range.  The normal cell budget
            does not truncate an exact range read.
        """
        _validate_density(density)
        sheet_info = _find_sheet(self.parsed_workbook, sheet)
        start_col, start_row, end_col, end_row = _parse_range(range_spec)
        selected_rows = _filter_rows(sheet_info.get("rows", []), start_col, start_row, end_col, end_row)
        return _render_grid(selected_rows, density, self.parsed_workbook, cell_budget=None)

    def find_cells(
        self,
        query: str,
        *,
        sheets: list[str] | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> str:
        """Search the loaded workbook for matching cell or defined-name data.

        Args:
            query: Text to find; matching is literal and case-sensitive.
            sheets: Optional worksheet names to search.  By default all sheets
                are searched.
            kind: Optional field filter: ``value``, ``formula``, ``comment``,
                ``hyperlink``, or ``definedName``.
            limit: Maximum number of matches to return.

        Returns:
            Match records in the parser's self-defined output format.
        """
        return _find_cells_in_workbook(self.parsed_workbook, query, sheets=sheets, kind=kind, limit=limit)

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
        """Query table or range data from the loaded workbook.

        Args:
            table_id: Declared table identifier to query.
            sheet: Worksheet name for an explicit range query.
            range_spec: A1-style range for an explicit range query.
            header_row: One-based row containing column headers.
            select: Column names to return.
            where: Conditions using ``eq``, ``contains``, ``gt``, or ``lt``.
            group_by: Column names used to group rows before aggregation.
            aggregates: Aggregate specifications such as ``sum`` or ``count``.
            order_by: Column and direction specifications; direction is
                ``asc`` or ``desc``.
            limit: Maximum number of result rows.

        Returns:
            Query results in the parser's self-defined tabular output format.
        """
        return _query_data(
            self.parsed_workbook,
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
        """Return one image, chart, or pivot-table resource by identifier.

        Args:
            resource_type: ``image``, ``chart``, or ``pivot_table``.
            resource_id: Resource identifier recorded in the workbook.

        Returns:
            The resource output, or ``None`` when the identifier is absent.
        """
        return _get_resource_from_workbook(self.parsed_workbook, resource_type, resource_id)


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
    """Parse an XLSX source and return the complete workbook output.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        start_row: One-based row at which rendering starts on the first data
            sheet; useful for paginating large sheets.
        stream: When true, return an iterator of output chunks.  Parsing still
            completes before the iterator is returned.
        options: Optional parser limits and feature configuration.

    Returns:
        A complete output string, or an iterator when ``stream`` is true.
    """
    _validate_density(density)
    parse_options = options or ParseOptions()
    parsed_workbook = _parse_workbook(source, parse_options, plan=XlsxParsePlan.render(density))
    if stream:
        return _iter_rendered_workbook(parsed_workbook, density, start_row)
    return "".join(_iter_rendered_workbook(parsed_workbook, density, start_row))


def iter_workbook(
    source: str | Path | bytes,
    *,
    density: str = "structural",
    start_row: int = 1,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Parse an XLSX source and yield workbook output chunks.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        start_row: One-based row at which rendering starts on the first data
            sheet.
        options: Optional parser limits and feature configuration.

    Returns:
        An iterator of output chunks.  Parsing completes before iteration.
    """
    _validate_density(density)
    parse_options = options or ParseOptions()
    parsed_workbook = _parse_workbook(source, parse_options, plan=XlsxParsePlan.render(density))
    return _iter_rendered_workbook(parsed_workbook, density, start_row)


def load_xlsx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> LoadedWorkbook:
    """Parse an XLSX source once and return a reusable workbook facade.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        options: Optional parser limits and feature configuration.

    Returns:
        A :class:`LoadedWorkbook` for repeated output and data operations.
    """
    parse_options = options or ParseOptions()
    parsed_workbook = _parse_workbook(source, parse_options, plan=XlsxParsePlan.session())
    return LoadedWorkbook(parsed_workbook, parse_options)


def _iter_rendered_workbook(parsed_workbook: ParsedWorkbook, density: str, start_row: int) -> Iterator[str]:
    """Yield output chunks for a parsed workbook."""
    yield f"density={density}\n"
    for sheet_index, sheet in enumerate(parsed_workbook["sheets"]):
        yield from _render_sheet(
            sheet,
            density,
            parsed_workbook,
            start_row=start_row,
            emit_globals=sheet_index == 0,
        )
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
    """Parse a source and render cells within an exact A1-style range.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        sheet: Worksheet name.
        range_spec: A1-style range such as ``A1:C20``.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        options: Optional parser limits and feature configuration.

    Returns:
        Output for exactly the requested range; the default cell budget does
        not truncate an exact range read.
    """
    _validate_density(density)
    parse_options = options or ParseOptions()
    start_col, start_row, end_col, end_row = _parse_range(range_spec)
    parsed_workbook = _parse_workbook(
        source,
        parse_options,
        plan=XlsxParsePlan.range(density, sheet, (start_col, start_row, end_col, end_row)),
    )
    sheet_info = _find_sheet(parsed_workbook, sheet)
    return _render_grid(sheet_info.get("rows", []), density, parsed_workbook, cell_budget=None)


def find_cells(
    source: str | Path | bytes,
    query: str,
    *,
    sheets: list[str] | None = None,
    kind: str | None = None,
    limit: int = 50,
    options: ParseOptions | None = None,
) -> str:
    """Search an XLSX source for matching cell or defined-name data.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        query: Text to find; matching is literal and case-sensitive.
        sheets: Optional worksheet names to search; defaults to all sheets.
        kind: Optional field filter: ``value``, ``formula``, ``comment``,
            ``hyperlink``, or ``definedName``.
        limit: Maximum number of matches to return.
        options: Optional parser limits and feature configuration.

    Returns:
        Match records in the parser's self-defined output format.
    """
    parse_options = options or ParseOptions()
    return _find_cells_in_workbook(
        _parse_workbook(source, parse_options, plan=XlsxParsePlan.session()),
        query,
        sheets=sheets,
        kind=kind,
        limit=limit,
    )


def _find_cells_in_workbook(
    parsed_workbook: ParsedWorkbook,
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
    sheets_to_search = sheets or [sheet["name"] for sheet in parsed_workbook["sheets"]]
    seen_names: set[str] = set()

    for sheet_name in sheets_to_search:
        if len(matches) >= limit:
            break
        sheet_info = _find_sheet(parsed_workbook, sheet_name)
        remaining = limit - len(matches)
        matches.extend(_find_cell_matches(sheet_info, sheet_name, pattern, kind, remaining))
        if len(matches) < limit and kind in {None, "definedName"}:
            remaining = limit - len(matches)
            defined_names = parsed_workbook["metadata"].get("defined_names", [])
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
    cell_ref = f"{escape_text(sheet_name, quote=True)}!{cell['ref']}"
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
            return f'<match cell="{cell_ref}" field={field_name}>{escape_text(value)}'
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
            escaped_name = escape_text(name)
            ref = escape_text(defined_name["ref"])
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
    """Query a declared table or explicit range in an XLSX source.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        table_id: Declared table identifier to query.
        sheet: Worksheet name for an explicit range query.
        range_spec: A1-style range for an explicit range query.
        header_row: One-based row containing column headers.
        select: Column names to return.
        where: Conditions using ``eq``, ``contains``, ``gt``, or ``lt``.
        group_by: Column names used to group rows before aggregation.
        aggregates: Aggregate specifications such as ``sum`` or ``count``.
        order_by: Column and direction specifications; direction is ``asc`` or
            ``desc``.
        limit: Maximum number of result rows.
        options: Optional parser limits and feature configuration.

    Returns:
        Query results in the parser's self-defined tabular output format.
    """
    parsed_workbook = load_xlsx(source, options=options).parsed_workbook
    return _query_data(
        parsed_workbook,
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
    """Parse an XLSX source and return one resource by identifier.

    Args:
        source: A filesystem path, path-like string, or XLSX bytes.
        resource_type: ``image``, ``chart``, ``pivot_table``, or
            ``embedded_object``.
        resource_id: Resource identifier recorded in the workbook.
        options: Optional parser limits and feature configuration.

    Returns:
        The resource output, or ``None`` when the identifier is absent.
    """
    parsed_workbook = load_xlsx(source, options=options).parsed_workbook
    return _get_resource_from_workbook(parsed_workbook, resource_type, resource_id)


def _get_resource_from_workbook(
    parsed_workbook: ParsedWorkbook,
    resource_type: str,
    resource_id: str,
) -> str | None:

    if resource_type == "image":
        for sheet_info in parsed_workbook["sheets"]:
            for image in sheet_info.get("images", []):
                if image["id"] == resource_id:
                    return f"<image id={resource_id} ref={image['ref']}/>"
    elif resource_type == "chart":
        for sheet_info in parsed_workbook["sheets"]:
            for chart in sheet_info.get("charts", []):
                if chart["id"] == resource_id:
                    return _render_chart_resource(chart)
    elif resource_type == "pivot_table":
        for sheet_info in parsed_workbook["sheets"]:
            for pivot_table in sheet_info.get("pivot_tables", []):
                if pivot_table["id"] == resource_id:
                    return f"<pivotTable id={resource_id} name={pivot_table.get('name', '')}/>"
    return None


def _render_chart_resource(chart: DrawingChart) -> str:
    """Render a chart as self-defined output with full series data."""

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
            category = point.get("category", "")
            value = point.get("value", "")
            if category:
                point_attrs += f" category={escape_text(category, quote=True)}"
            if value:
                point_attrs += f" value={escape_text(value, quote=True)}"
            if point.get("x"):
                point_attrs += f" x={escape_text(point['x'], quote=True)}"
            if point.get("y"):
                point_attrs += f" y={escape_text(point['y'], quote=True)}"
            if point.get("bubbleSize"):
                point_attrs += f" bubbleSize={escape_text(point['bubbleSize'], quote=True)}"
            parts.append(f"\n<point{point_attrs}/>")

    return "".join(parts)
