"""Direct low-noise plain-text rendering for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape as escape_text

from doctokens_core.ooxml.charts.preview import plain_chart
from doctokens_core.runtime.execution import checkpoint

from ..model.workbook import Cell, ParsedWorkbook, SheetInfo, TableInfo
from .window import ReadingWindow, reading_window


def iter_plain(workbook: ParsedWorkbook) -> Iterator[str]:
    """Render workbook text in reading order with the existing sheet boundaries."""
    for sheet in workbook["sheets"]:
        yield from _iter_sheet(sheet)


def iter_plain_rows(rows: list[list[Cell]], *, hidden_cols: list[tuple[int, int]] | None = None) -> Iterator[str]:
    """Render selected rows as tab-separated visible values."""
    for row in rows:
        checkpoint("rendering worksheet rows")
        if not row:
            continue
        values = [_cell_text(cell) for cell in row if not _hidden_column(cell["col"], hidden_cols)]
        yield "\t".join(values) + "\n"


def iter_plain_window(window: ReadingWindow, sheet: SheetInfo) -> Iterator[str]:
    yield from iter_plain_rows(window.rows, hidden_cols=sheet.get("hidden_cols", []))
    if window.truncated:
        yield f"[Truncated: next row {window.next_row}]\n"


def _iter_sheet(sheet: SheetInfo) -> Iterator[str]:
    name = escape_text(sheet["name"], quote=True)
    attrs = f"name={name}"
    state = sheet.get("state", "visible")
    if state == "hidden":
        attrs += " hidden"
    elif state == "veryHidden":
        attrs += " veryHidden"
    is_chart_sheet = sheet.get("kind") == "chartsheet"
    yield f"<{'chartsheet' if is_chart_sheet else 'sheet'} {attrs}>\n"
    if sheet.get("filter_range") and sheet.get("filter_cols"):
        yield f"[Filter {sheet['filter_range']}]\n"
    for validation in sheet.get("data_validations", []):
        if validation.get("unparsed"):
            yield "[Unparsed data validation]\n"
    for condition in sheet.get("conditional_formats", []):
        if condition.get("unparsed"):
            yield "[Unparsed conditional format]\n"
    for image in sheet.get("images", []):
        description = f": {image['alt']}" if image.get("alt") else ""
        yield f"[Image {image['id']} at {image['ref']}{description}]\n"
        if image.get("unparsed"):
            yield "[Unparsed image]\n"
    for chart in sheet.get("charts", []):
        yield (
            plain_chart(
                chart.get("id"),
                chart.get("type", "?"),
                chart.get("title"),
                [item["name"] for item in chart.get("series", []) if item.get("name")],
                chart.get("series_count", 0),
            )
            + "\n"
        )
        if chart.get("unparsed"):
            yield "[Unparsed chart]\n"
    for shape in sheet.get("drawing_shapes", []):
        if shape["kind"] == "unsupported":
            yield f"[Unparsed drawing: {shape.get('name', 'object')}]\n"
        elif shape.get("text"):
            yield shape["text"] + "\n"
        elif shape.get("alt") or shape.get("title"):
            yield f"[Shape: {shape.get('alt') or shape.get('title')}]\n"
    for pivot in sheet.get("pivot_tables", []):
        yield f"[PivotTable{' ' + pivot['name'] if pivot.get('name') else ''}]\n"
    for table in sheet.get("tables", []):
        yield _table_summary(table)
    if not is_chart_sheet:
        yield from iter_plain_window(reading_window(sheet, "plain"), sheet)


def _hidden_column(column: int, ranges: list[tuple[int, int]] | None) -> bool:
    return bool(ranges and any(first <= column <= last for first, last in ranges))


def _cell_text(cell: Cell) -> str:
    control = cell.get("cellControl")
    if control and control.get("kind") == "checkbox":
        value = control.get("state", cell["text"])
        value = f"[Checkbox {value}]"
    elif rich_value := cell.get("richValue"):
        if rich_value.get("imageStatus") == "unbound":
            description = rich_value.get("alt") or rich_value.get("display") or rich_value.get("fallback")
            value = f"[Image unavailable: {description}]" if description else "[Image unavailable]"
            saved = cell["text"]
            if saved.strip() and saved != description:
                value += " " + saved
        elif rich_value.get("imagePart") or rich_value.get("imageUrl"):
            value = str(rich_value.get("alt") or rich_value.get("display") or "[Image]")
        else:
            value = str(rich_value.get("display") or rich_value.get("fallback") or cell["text"])
    else:
        value = cell["text"]
    comments: list[str] = []
    if cell.get("comment") is not None:
        comments.append(f"[comment status=unknown] {cell['comment']}".rstrip())
    comments.extend(
        f"[comment status={comment.get('status', 'unknown')}] {comment.get('text', '')}".rstrip()
        for comment in cell.get("threadedComments", [])
    )
    suffix = " ".join(comments)
    return value + (" " if value and suffix else "") + suffix


def _table_summary(table: TableInfo) -> str:
    label = " ".join(value for value in (table.get("name"), table.get("ref")) if value)
    return f"[Table {label}]\n" if label else "[Table]\n"


__all__ = ["iter_plain", "iter_plain_rows"]
