"""Direct low-noise plain-text rendering for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape as escape_text
from typing import cast

from ..models import Cell, ParsedWorkbook, SheetInfo


def iter_plain(workbook: ParsedWorkbook) -> Iterator[str]:
    """Render workbook text in reading order with the existing sheet boundaries."""
    yield "density=plain\n"
    for index, sheet in enumerate(workbook["sheets"]):
        yield from _iter_sheet(sheet, workbook, emit_globals=index == 0)


def iter_plain_rows(rows: list[list[Cell]], *, hidden_cols: list[tuple[int, int]] | None = None) -> Iterator[str]:
    """Render selected rows as tab-separated visible values."""
    for row in rows:
        if not row:
            continue
        values = [_cell_text(cell) for cell in row if not _hidden_column(cell["col"], hidden_cols)]
        yield "\t".join(values) + "\n"


def _iter_sheet(sheet: SheetInfo, workbook: ParsedWorkbook, *, emit_globals: bool) -> Iterator[str]:
    name = escape_text(sheet["name"], quote=True)
    if sheet.get("kind") == "chartsheet":
        yield f"<chartsheet name={name}>\n"
        return
    attrs = f"name={name}"
    state = sheet.get("state", "visible")
    if state == "hidden":
        attrs += " hidden"
    elif state == "veryHidden":
        attrs += " veryHidden"
    yield f"<sheet {attrs}>\n"
    if sheet.get("filter_range"):
        yield f"[Filter {sheet['filter_range']}]\n"
    if emit_globals:
        yield from _iter_interactive_filters(workbook)
    for image in sheet.get("images", []):
        yield f"[Image {image['id']} at {image['ref']}]\n"
    for chart in sheet.get("charts", []):
        title = f" {chart['title']}" if chart.get("title") else ""
        names = ", ".join(_chart_names(chart))
        yield f"[Chart{title}{': ' + names if names else ''}]\n"
    for pivot in sheet.get("pivot_tables", []):
        yield f"[PivotTable{' ' + pivot['name'] if pivot.get('name') else ''}]\n"
    for table in sheet.get("tables", []):
        yield _table_summary(table)
    yield from iter_plain_rows(sheet.get("rows", []), hidden_cols=sheet.get("hidden_cols", []))


def _hidden_column(column: int, ranges: list[tuple[int, int]] | None) -> bool:
    return bool(ranges and any(first <= column <= last for first, last in ranges))


def _cell_text(cell: Cell) -> str:
    control = cell.get("cellControl")
    if control and control.get("kind") == "checkbox":
        value = control.get("state", cell["text"])
        return f"[Checkbox {value}]"
    rich_value = cell.get("richValue")
    if rich_value:
        if rich_value.get("imagePart") or rich_value.get("imageUrl"):
            return str(rich_value.get("alt") or rich_value.get("display") or "[Image]")
        return str(rich_value.get("display") or rich_value.get("fallback") or cell["text"])
    value = cell["text"]
    comments: list[str] = []
    if cell.get("comment") is not None:
        author = cell.get("commentAuthor", "")
        comments.append(f"[Comment{' by ' + author if author else ''}: {cell['comment']}]")
    for comment in cell.get("threadedComments", []):
        qualifiers = [str(comment["author"])] if comment.get("author") else []
        if comment.get("parentId"):
            qualifiers.append("reply")
        if comment.get("resolved"):
            qualifiers.append("resolved")
        label = f" ({', '.join(qualifiers)})" if qualifiers else ""
        comments.append(f"[Comment{label}: {comment.get('text', '')}]")
    return value + (" " + " ".join(comments) if comments else "")


def _iter_interactive_filters(workbook: ParsedWorkbook) -> Iterator[str]:
    metadata = workbook["metadata"]
    for slicer in metadata.get("slicers", []):
        name = slicer.get("name") or slicer.get("sourceName")
        yield f"[Slicer {name}]\n" if name else "[Slicer]\n"
    for timeline in metadata.get("timelines", []):
        name = timeline.get("name") or timeline.get("sourceName")
        yield f"[Timeline {name}]\n" if name else "[Timeline]\n"


def _chart_names(chart: object) -> list[str]:
    if not isinstance(chart, dict):
        return []
    series = chart.get("series")
    if not isinstance(series, list):
        return []
    return [str(item.get("name")) for item in cast(list[object], series) if isinstance(item, dict) and item.get("name")]


def _table_summary(table: object) -> str:
    if not isinstance(table, dict):
        return "[Table]\n"
    name = table.get("name")
    raw_columns = table.get("columns")
    columns = cast(list[object], raw_columns) if isinstance(raw_columns, list) else []
    listed = ", ".join(str(column) for column in columns if column)
    if name and listed:
        return f"[Table {name}: {listed}]\n"
    if name:
        return f"[Table {name}]\n"
    if listed:
        return f"[Table: {listed}]\n"
    return "[Table]\n"


__all__ = ["iter_plain", "iter_plain_rows"]
