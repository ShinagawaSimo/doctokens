"""Table rendering (structural/semantic): full tables, truncated tables, rows, cells, nested tables."""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ...core.models import TableBlock, TableCell, TableRow
from .. import _constants
from ..inline import inline_content


def render_table(block: TableBlock, density: str) -> Iterator[str]:
    """Output an HTML5 table (for structural/semantic). Cells within a row have no newlines; only rows are newline-separated."""
    rows = block.get("rows", [])

    if len(rows) > _constants._TABLE_TRUNCATE_STRUCTURAL_SEMANTIC:
        yield from render_truncated_table(block, rows, density)
        return

    yield f"<table id={table_id(block)}>\n"
    for row in rows:
        yield render_table_row(row, density) + "\n"


def render_truncated_table(block: TableBlock, rows: list[TableRow], density: str) -> Iterator[str]:
    """Output a truncated table (for structural/semantic): header row + first row."""
    yield f"<table id={table_id(block)} truncated>\n"
    yield render_table_row(rows[0], density) + "\n"
    if len(rows) > 1:
        yield render_table_row(rows[1], density) + "\n"


def table_id(block: TableBlock) -> str:
    """Return the stable logical table ID assigned during parsing."""
    value = block["tableId"]
    if not isinstance(value, str):
        raise TypeError("table block field 'tableId' must be a string")
    return value


def render_table_row(row: TableRow, density: str) -> str:
    """Render one table row. structural keeps merge structure and nested tables."""
    row_tag = "<tr h>" if row.get("isHeader") else "<tr>"
    parts = [row_tag]

    for cell in row["cells"]:
        cell_tag = "th" if row.get("isHeader") else "td"

        if density in {"structural", "semantic"}:
            attrs_parts: list[str] = [cell_tag]
            if cell["colSpan"] != 1:
                attrs_parts.append(f"colspan={cell['colSpan']}")
            if cell["rowSpan"] != 1:
                attrs_parts.append(f"rowspan={cell['rowSpan']}")
            if cell.get("vMerge"):
                attrs_parts.append(f"vmerge={cell['vMerge']}")
            tag = " ".join(attrs_parts)
        else:
            tag = cell_tag

        cell_text = cell_content(cell, density)
        parts.append(f"<{tag}>{cell_text}")

    return "".join(parts)


def cell_content(cell: TableCell, density: str) -> str:
    """Output the cell text."""
    blocks = cell.get("blocks", [])
    if not blocks:
        return escape(cell["text"])
    parts: list[str] = []
    for block in blocks:
        if block["type"] == "table":
            if density in {"structural", "semantic"}:
                parts.append(nested_table(block))
        else:
            parts.append(inline_content(block, density))
    return "\n".join(part for part in parts if part)


def nested_table(block: TableBlock) -> str:
    """Render a nested table as lightweight HTML5."""
    rows = block["rows"]
    attrs = f"rows={len(rows)} cols={block['columnCount']}"
    table_id_value = block.get("tableId")
    if isinstance(table_id_value, str) and table_id_value:
        attrs = f"id={table_id_value} {attrs}"
    parts = [f"<nestedtable {attrs}>"]
    for row in rows:
        tag = "<row header>" if row.get("isHeader") else "<row>"
        parts.append(tag)
        for cell in row["cells"]:
            c_tag = "th" if row.get("isHeader") else "td"
            attrs_parts: list[str] = [c_tag]
            if cell["colSpan"] != 1:
                attrs_parts.append(f"colspan={cell['colSpan']}")
            if cell["rowSpan"] != 1:
                attrs_parts.append(f"rowspan={cell['rowSpan']}")
            if cell.get("vMerge"):
                attrs_parts.append(f"vmerge={cell['vMerge']}")
            attrs = " ".join(attrs_parts)
            parts.append(f"<{attrs}>{cell_content(cell, 'semantic')}")
    return "".join(parts)
