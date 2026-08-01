"""表格渲染（L1/L2）：完整表格、截断表格、行、单元格、嵌套表格。"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from ...core.models import TableBlock, TableCell, TableRow
from .. import _constants
from ..inline import inline_content


def render_table(block: TableBlock, density: str) -> Iterator[str]:
    """输出 HTML5 表格（L1/L2 用）。行内单元格无换行，仅行间换行。"""
    rows = block.get("rows", [])

    if len(rows) > _constants._TABLE_TRUNCATE_L12:
        yield from render_truncated_table(block, rows, density)
        return

    yield "<table>\n"
    for row in rows:
        yield render_table_row(row, density) + "\n"


def render_truncated_table(block: TableBlock, rows: list[TableRow], density: str) -> Iterator[str]:
    """输出截断表格（L1/L2 用）：表头行 + 首行 + 截断提示。"""
    total_rows = len(rows)
    yield "<table>\n"
    yield render_table_row(rows[0], density) + "\n"
    if len(rows) > 1:
        yield render_table_row(rows[1], density) + "\n"
    yield f'<!-- {total_rows} rows truncated. Use extract("table", "{table_id(block)}") -->\n'


def table_id(block: TableBlock) -> str:
    """Return the stable logical table ID assigned during parsing."""
    value = block["tableId"]
    if not isinstance(value, str):
        raise TypeError("table block field 'tableId' must be a string")
    return value


def render_table_row(row: TableRow, density: str) -> str:
    """渲染一行表格。L1 忽略 colspan/rowspan/vMerge。"""
    row_tag = "<tr h>" if row.get("isHeader") else "<tr>"
    parts = [row_tag]

    for cell in row["cells"]:
        cell_tag = "th" if row.get("isHeader") else "td"

        if density == "L2":
            attrs_parts: list[str] = [cell_tag]
            if cell["colSpan"] != 1:
                attrs_parts.append(f"s={cell['colSpan']}")
            if cell["rowSpan"] != 1:
                attrs_parts.append(f"rs={cell['rowSpan']}")
            if cell.get("vMerge"):
                attrs_parts.append(f"v={cell['vMerge']}")
            tag = " ".join(attrs_parts)
        else:
            tag = cell_tag

        cell_text = cell_content(cell, density)
        parts.append(f"<{tag}>{cell_text}")

    return "".join(parts)


def cell_content(cell: TableCell, density: str) -> str:
    """输出单元格文本。"""
    blocks = cell.get("blocks", [])
    if not blocks:
        return escape(cell["text"])
    parts: list[str] = []
    for block in blocks:
        if block["type"] == "table":
            if density == "L2":
                parts.append(nested_table(block))
        else:
            parts.append(inline_content(block, density))
    return "\n".join(part for part in parts if part)


def nested_table(block: TableBlock) -> str:
    """L2：把嵌套表格渲染为轻量 HTML5。"""
    rows = block["rows"]
    parts = [f"<ntable r={len(rows)} c={block['columnCount']}>"]
    for row in rows:
        tag = "<r h>" if row.get("isHeader") else "<r>"
        parts.append(tag)
        for cell in row["cells"]:
            c_tag = "th" if row.get("isHeader") else "td"
            attrs_parts: list[str] = [c_tag]
            if cell["colSpan"] != 1:
                attrs_parts.append(f"s={cell['colSpan']}")
            if cell["rowSpan"] != 1:
                attrs_parts.append(f"rs={cell['rowSpan']}")
            if cell.get("vMerge"):
                attrs_parts.append(f"v={cell['vMerge']}")
            attrs = " ".join(attrs_parts)
            parts.append(f"<{attrs}>{cell_content(cell, 'L2')}")
    return "".join(parts)
