"""Public API — accepts source files directly, returns rendered results."""

from __future__ import annotations

import os
from collections.abc import Iterator
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import Cell, DrawingChart
from .parser import _parse_workbook
from .query import AggregateSpec, OrderSpec, WhereCondition
from .query import query_data as _query_data
from .renderers.structural import (
    _find_sheet,
    _parse_range,
    _render_grid,
    _render_sheet,
)


def parse_xlsx(
    source: str | Path | bytes,
    *,
    density: str = "structural",
    start_row: int = 1,
    stream: bool = False,
) -> str | Iterator[str]:
    """Parse *source* and render the entire workbook at the given density.

    Returns a string by default.  Set *stream=True* to receive an iterator
    of rendered chunks for streaming output or large workbooks.

    *start_row* (1-based) begins rendering from the specified row for the
    first data sheet, enabling paginated window reads of large grids.
    """
    wb = _parse_workbook(source)
    if stream:
        return _generate_workbook(wb, density, start_row)
    return "".join(_generate_workbook(wb, density, start_row))


def _generate_workbook(wb: dict, density: str, start_row: int) -> Iterator[str]:
    """Yield rendered chunks for a parsed workbook."""
    yield f"density={density}\n"
    for sheet in wb["sheets"]:
        yield from _render_sheet(sheet, density, wb, start_row=start_row)
        if sheet.get("kind") != "chartsheet" and start_row != 1:
            start_row = 1


def write_document(
    source: str | Path | bytes,
    output_dir: str | Path,
    *,
    density: str = "structural",
    start_row: int = 1,
) -> Path:
    """Parse *source* and write the rendered file to *output_dir* (atomic write)."""
    from pathlib import Path as _Path

    output_dir = _Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "parsed.html"
    temp_path: _Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=output_dir, prefix=".parsed.html.", suffix=".tmp", delete=False
        ) as stream:
            temp_path = _Path(stream.name)
            for chunk in _generate_workbook(_parse_workbook(source), density, start_row):
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(output_path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise
    return output_path


def render_range(
    source: str | Path | bytes,
    sheet: str,
    range_spec: str,
    *,
    density: str = "structural",
) -> str:
    """Render cells within an A1-style range from *source*."""
    wb = _parse_workbook(source)
    sheet_info = _find_sheet(wb, sheet)
    start_col, start_row, end_col, end_row = _parse_range(range_spec)

    rows = sheet_info.get("rows", [])
    filtered: list[list[Cell]] = []
    for row_cells in rows:
        kept = [c for c in row_cells if start_col <= c["col"] <= end_col and start_row <= c["row"] <= end_row]
        if kept:
            filtered.append(kept)

    return _render_grid(filtered, density, wb)


def find_cells(
    source: str | Path | bytes,
    query: str,
    *,
    sheets: list[str] | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> str:
    """Search values, formulas, comments, hyperlinks, and defined names across sheets.

    *kind* narrows to one of ``value``, ``formula``, ``comment``, ``hyperlink``,
    ``definedName``.
    """
    import re as _re

    if not query:
        return "<matches>\n"
    wb = _parse_workbook(source)
    pattern = _re.compile(_re.escape(query))  # exact match by default
    matches: list[str] = []
    sheets_to_search = sheets or [s["name"] for s in wb["sheets"]]

    for sheet_name in sheets_to_search:
        if len(matches) >= limit:
            break
        sheet = _find_sheet(wb, sheet_name)
        for row_cells in sheet.get("rows", []):
            for cell in row_cells:
                if len(matches) >= limit:
                    break
                cell_ref = f"{escape(sheet_name, quote=True)}!{cell['ref']}"
                if (kind is None or kind == "value") and pattern.search(cell.get("text", "")):
                    matches.append(f'<match cell="{cell_ref}" field=value>{escape(cell["text"])}')
                    continue
                if (kind is None or kind == "formula") and pattern.search(cell.get("formula", "")):
                    matches.append(f'<match cell="{cell_ref}" field=formula>{escape(cell.get("formula", ""))}')
                    continue
                if (kind is None or kind == "comment") and pattern.search(cell.get("comment", "")):
                    matches.append(f'<match cell="{cell_ref}" field=comment>{escape(cell.get("comment", ""))}')
                    continue
                if (kind is None or kind == "hyperlink") and pattern.search(cell.get("hyperlink", "")):
                    matches.append(f'<match cell="{cell_ref}" field=hyperlink>{escape(cell.get("hyperlink", ""))}')
            if len(matches) >= limit:
                break

        # Defined names
        if (kind is None or kind == "definedName") and len(matches) < limit:
            for dn in wb["metadata"].get("defined_names", []):
                if len(matches) >= limit:
                    break
                scope = dn.get("scopeSheet")
                if scope and scope != sheet_name:
                    continue
                if pattern.search(dn["name"]) or pattern.search(dn.get("ref", "")):
                    matches.append(f"<match field=definedName>{escape(dn['name'])} = {escape(dn['ref'])}")

    parts = ["<matches>\n"]
    parts.append("\n".join(matches[:limit]))
    return "".join(parts) + "\n"


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
) -> str:
    """Query a declared Table or explicit range with projection, filtering,
    grouping, and aggregation.  Returns lightweight tabular HTML.
    """
    wb = _parse_workbook(source)
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
) -> str | None:
    """Return a resource by type and ID as an HTML string for LLM consumption.

    *resource_type*: ``image``, ``chart``, ``pivot_table``, ``embedded_object``.
    """
    wb = _parse_workbook(source)

    if resource_type == "image":
        for s in wb["sheets"]:
            for img in s.get("images", []):
                if img["id"] == resource_id:
                    return f"<image id={resource_id} ref={img['ref']}/>"
    elif resource_type == "chart":
        for s in wb["sheets"]:
            for ch in s.get("charts", []):
                if ch["id"] == resource_id:
                    return _render_chart_resource(ch)
    elif resource_type == "pivot_table":
        for s in wb["sheets"]:
            for pv in s.get("pivot_tables", []):
                if pv["id"] == resource_id:
                    return f"<pivotTable id={resource_id} name={pv.get('name', '')}/>"
    return None


def _render_chart_resource(ch: DrawingChart) -> str:
    """Render a chart as an HTML string — full series data."""
    from html import escape

    attrs = f"id={ch['id']} ref={ch['ref']} type={ch.get('type', '?')}"
    attrs += f" series={ch.get('series_count', 0)}"
    if ch.get("title"):
        attrs += f" title={escape(ch['title'], quote=True)}"
    parts = [f"<chart {attrs}>"]

    for s in ch.get("series", []):
        s_attrs = f"index={s.get('index', 0)}"
        if s.get("name"):
            s_attrs += f" name={escape(s['name'], quote=True)}"
        if "min" in s:
            s_attrs += f" min={s['min']}"
        if "max" in s:
            s_attrs += f" max={s['max']}"
        parts.append(f"\n<series {s_attrs}>")
        for pt in s.get("points", []):
            pt_attrs = ""
            cat = pt.get("category", "")
            val = pt.get("value", "")
            if cat:
                pt_attrs += f" category={escape(cat, quote=True)}"
            if val:
                pt_attrs += f" value={escape(val, quote=True)}"
            parts.append(f"\n<point{pt_attrs}/>")

    return "".join(parts)
