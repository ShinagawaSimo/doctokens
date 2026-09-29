"""Parse DOCX tables, including nested blocks and page-separated segments."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from ....core.constants import _TAG_W_PARAGRAPH, _TAG_W_TABLE, attr, child_elements, first_child, local_name
from ....core.models import Block, ContentControl, TableBlock, TableCell, TableRow


class TableParser:
    """Own table geometry, merge state, and table-local pagination."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def parse(
        self,
        table: ET.Element,
        part: str,
        content_controls: tuple[ContentControl, ...] = (),
    ) -> list[TableBlock]:
        """Parse a table into one block per row-level page segment."""
        self.owner._order += 1
        section_index = self.owner._sections._begin_section()
        table_id = self._next_table_id()
        segment_page = self.owner._flush_pending_page_breaks()

        sub_tables: list[TableBlock] = []
        segment_rows: list[TableRow] = []
        merge_state: dict[int, TableCell] = {}
        widest_column_count = 0
        page_before_row = self.owner._page_hint

        for row_index, row_element in enumerate(child_elements(table, "w", "tr")):
            row, row_width = self._parse_row(row_element, row_index, part)
            widest_column_count = max(widest_column_count, row_width)
            if self.owner._page_hint != page_before_row:
                if segment_rows:
                    self.apply_vertical_merges(segment_rows, merge_state)
                    sub_tables.append(
                        self._make_block(
                            part,
                            segment_page,
                            segment_rows,
                            widest_column_count,
                            table_id,
                            len(sub_tables) + 1,
                            section_index,
                            content_controls,
                        )
                    )
                    segment_page = self.owner._page_hint
                    segment_rows = []
                self.owner._pending_page_breaks = 0
            segment_rows.append(row)
            page_before_row = self.owner._page_hint

        if segment_rows:
            self.apply_vertical_merges(segment_rows, merge_state)
            sub_tables.append(
                self._make_block(
                    part,
                    segment_page,
                    segment_rows,
                    widest_column_count,
                    table_id,
                    len(sub_tables) + 1,
                    section_index,
                    content_controls,
                )
            )

        table_end = max((self._block_end_page(block) for block in sub_tables), default=segment_page)
        self.owner._page_hint = max(self.owner._page_hint, table_end)
        return sub_tables

    def _make_block(
        self,
        part: str,
        page: int,
        rows: list[TableRow],
        max_col: int,
        table_id: str,
        segment_index: int,
        section_index: int,
        content_controls: tuple[ContentControl, ...],
    ) -> TableBlock:
        block_id = self.owner.block_ids.allocate()
        block: TableBlock = {
            "id": block_id,
            "type": "table",
            "part": part,
            "order": self.owner._order,
            "page": page,
            "tableId": table_id,
            "segmentIndex": segment_index,
            "rows": rows,
            "columnCount": max_col,
            "section": section_index,
        }
        if content_controls:
            block["contentControls"] = list(content_controls)
        block_end = max(
            (self._block_end_page(child) for row in rows for cell in row["cells"] for child in cell["blocks"]),
            default=page,
        )
        if block_end > page:
            block["pageEnd"] = block_end
        return block

    def _block_end_page(self, block: Block) -> int:
        end_page = int(block.get("pageEnd", block.get("page", 1)))
        if block["type"] == "table":
            for row in block["rows"]:
                for cell in row["cells"]:
                    for child in cell["blocks"]:
                        end_page = max(end_page, self._block_end_page(child))
        return end_page

    def _parse_row(self, row_element: ET.Element, row_index: int, part: str) -> tuple[TableRow, int]:
        cells: list[TableCell] = []
        next_column = 0
        is_header = first_child(first_child(row_element, "w", "trPr"), "w", "tblHeader") is not None
        for cell_element in child_elements(row_element, "w", "tc"):
            col_span = self._cell_col_span(cell_element)
            vertical_merge = self._cell_v_merge(cell_element)
            cell_blocks = self._parse_cell_blocks(cell_element, part)
            cell: TableCell = {
                "rowIndex": row_index,
                "colIndex": next_column,
                "rowSpan": 1,
                "colSpan": col_span,
                "text": self._cell_text(cell_blocks),
                "blocks": cell_blocks,
            }
            if vertical_merge:
                cell["vMerge"] = vertical_merge
            cells.append(cell)
            next_column += col_span
        row: TableRow = {"rowIndex": row_index, "cells": cells}
        if is_header:
            row["isHeader"] = True
        return row, next_column

    def _next_table_id(self) -> str:
        self.owner._table_index += 1
        return f"t{self.owner._table_index}"

    def _parse_cell_blocks(self, cell: ET.Element, part: str) -> list[Block]:
        blocks: list[Block] = []
        for child in cell:
            child_tag = child.tag
            if child_tag == _TAG_W_PARAGRAPH:
                block = self.owner.parse_paragraph(child, part)
                if block is not None:
                    blocks.append(block)
            elif child_tag == _TAG_W_TABLE:
                blocks.extend(self.owner.parse_table(child, part))
            elif local_name(child_tag) == "sdt":
                self.owner._parse_sdt(child, blocks)
        return blocks

    def _cell_col_span(self, cell: ET.Element) -> int:
        grid_span = first_child(first_child(cell, "w", "tcPr"), "w", "gridSpan")
        value = attr(grid_span, "w", "val") if grid_span is not None else None
        if value is None:
            return 1
        try:
            return max(1, int(value))
        except ValueError:
            self.owner._warn("INVALID_GRID_SPAN", f"Invalid gridSpan value: {value!r}", part="word/document.xml")
            return 1

    @staticmethod
    def _cell_v_merge(cell: ET.Element) -> str | None:
        vmerge = first_child(first_child(cell, "w", "tcPr"), "w", "vMerge")
        if vmerge is None:
            return None
        return attr(vmerge, "w", "val") or "continue"

    @staticmethod
    def _cell_text(blocks: list[Block]) -> str:
        parts: list[str] = []
        for block in blocks:
            if block["type"] in {"paragraph", "heading"} and block["text"]:
                parts.append(block["text"])
            elif block["type"] == "table":
                for row in block["rows"]:
                    text = " | ".join(cell["text"] for cell in row["cells"])
                    if text.strip():
                        parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def apply_vertical_merges(rows: list[TableRow], active: dict[int, TableCell] | None = None) -> None:
        """Add rowSpan to vertical merge origins across page-separated segments."""
        if active is None:
            active = {}
        for row in rows:
            for cell in row["cells"]:
                columns = range(cell["colIndex"], cell["colIndex"] + cell["colSpan"])
                v_merge = cell.get("vMerge")
                if v_merge == "restart":
                    for column in columns:
                        active[column] = cell
                elif v_merge == "continue":
                    origins: list[TableCell] = []
                    for column in columns:
                        origin = active.get(column)
                        if origin is not None and origin not in origins:
                            origins.append(origin)
                    for origin in origins:
                        origin["rowSpan"] += 1
                else:
                    for column in columns:
                        active.pop(column, None)
