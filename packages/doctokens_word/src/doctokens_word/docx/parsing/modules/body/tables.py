"""Parse selected table geometry, controls, styles and structural revisions."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ....model import Block, ContentControl, TableBlock, TableCell, TableRow
from ....ooxml.formatting import normalize_hex_color
from ....ooxml.namespaces import attr, first_child, local_name, qualified_name
from ....ooxml.property_changes import apply_property_review, selected_properties, structural_revision
from ....ooxml.table_styles import TableStyleResolver
from .containers import container_blocks
from .table_geometry import RowSource, apply_vertical_merges, table_rows, vertical_merge

if TYPE_CHECKING:
    from .scanner import DocumentBodyParser


class TableParser:
    def __init__(self, owner: DocumentBodyParser) -> None:
        self.owner = owner

    def parse(self, table: ET.Element, part: str, content_controls: tuple[ContentControl, ...] = ()) -> list[TableBlock]:
        owner = self.owner
        owner._order += 1
        section = owner._sections._begin_section()
        table_id = owner.table_ids.allocate()
        page = owner._flush_pending_page_breaks()
        view = str(owner.options.revision_mode)
        sources = table_rows(table, view, owner.warnings, part, owner.options.max_table_columns)
        grid = selected_properties(first_child(table, "w", "tblGrid"), view)
        columns = max(
            len(grid.findall(qualified_name("w", "gridCol"))) if grid is not None else 0,
            max((row.width for row in sources), default=0),
        )
        current_properties = first_child(table, "w", "tblPr")
        properties = selected_properties(current_properties, view)
        headers = next((index for index, row in enumerate(sources) if not row.header), len(sources))
        styles = TableStyleResolver(owner.styles, properties, len(sources), columns, headers)
        blocks: list[TableBlock] = []
        rows: list[TableRow] = []
        active: dict[int, TableCell] = {}

        def emit() -> None:
            if not rows:
                return
            apply_vertical_merges(rows, active)
            block: TableBlock = {
                "id": owner.block_ids.allocate(),
                "type": "table",
                "part": part,
                "order": owner._order,
                "page": page,
                "tableId": table_id,
                "segmentIndex": len(blocks) + 1,
                "rows": list(rows),
                "columnCount": columns,
                "section": section,
            }
            if content_controls:
                block["contentControls"] = list(content_controls)
            apply_property_review(block, current_properties, "table", view)
            grid_change = first_child(grid, "w", "tblGridChange")
            if view == "review" and grid_change is not None:
                from ....ooxml.property_changes import property_change

                old_grid = selected_properties(grid, "original")
                change = property_change(
                    grid,
                    "table",
                    {"columns": len(old_grid.findall(qualified_name("w", "gridCol"))) if old_grid is not None else 0},
                    {"columns": columns},
                )
                if change:
                    block.setdefault("propertyChanges", []).append(change)
            end = max((self._end(child) for row in rows for cell in row["cells"] for child in cell["blocks"]), default=page)
            if end > page:
                block["pageEnd"] = end
            blocks.append(block)

        before = owner._page_hint
        for index, source in enumerate(sources):
            row = self._row(source, index, part, styles)
            if owner._page_hint != before:
                if rows:
                    emit()
                    rows.clear()
                    page = owner._page_hint
                owner._pending_page_breaks = 0
            rows.append(row)
            before = owner._page_hint
        emit()
        owner._page_hint = max(owner._page_hint, max((self._end(block) for block in blocks), default=page))
        return blocks

    def _row(self, source: RowSource, index: int, part: str, styles: TableStyleResolver) -> TableRow:
        owner = self.owner
        view = str(owner.options.revision_mode)
        row: TableRow = {"rowIndex": index, "cells": []}
        if source.header:
            row["isHeader"] = True
        if source.before:
            row["gridBefore"] = source.before
        if source.after:
            row["gridAfter"] = source.after
        if source.controls:
            row["contentControls"] = list(source.controls)
        row_pr = first_child(source.node, "w", "trPr")
        apply_property_review(row, row_pr, "row", view)
        exceptions = first_child(source.node, "w", "tblPrEx")
        apply_property_review(row, exceptions, "row-table", view)
        styles = styles.row_exception(selected_properties(exceptions, view))
        revision = structural_revision(row_pr)
        deleted_row = revision is not None and local_name(revision.tag) in {"del", "moveFrom"}
        for cell_source in source.cells:
            cell_pr = first_child(cell_source.node, "w", "tcPr")
            cell_revision = structural_revision(cell_pr)
            deleted_cell = cell_revision is not None and local_name(cell_revision.tag) == "cellDel"
            outer_style = owner.inline.table_style
            outer_resolver = owner.inline.table_style_for_paragraph
            owner.inline.table_style = styles.cell(
                index, cell_source.column, cell_source.span, source.properties, cell_source.properties
            )
            owner.inline.table_style_for_paragraph = partial(
                styles.cell, index, cell_source.column, cell_source.span, source.properties, cell_source.properties
            )
            owner.inline.revisions.deleted_depth += int(deleted_row or deleted_cell)
            try:
                blocks = container_blocks(owner, cell_source.node, part)
                background = owner.inline.table_style.cell_background
            finally:
                owner.inline.table_style = outer_style
                owner.inline.table_style_for_paragraph = outer_resolver
                owner.inline.revisions.deleted_depth -= int(deleted_row or deleted_cell)
            cell: TableCell = {
                "rowIndex": index,
                "colIndex": cell_source.column,
                "rowSpan": 1,
                "colSpan": cell_source.span,
                "text": self._cell_text(blocks),
                "blocks": blocks,
            }
            merge = vertical_merge(cell_source.properties, view)
            if merge:
                cell["vMerge"] = merge
            if cell_source.controls:
                cell["contentControls"] = list(cell_source.controls)
            shading = first_child(cell_source.properties, "w", "shd")
            if shading is not None:
                background = normalize_hex_color(attr(shading, "w", "fill"))
                if attr(shading, "w", "val") == "nil":
                    background = None
            if background and owner.include_character_formatting:
                cell["background"] = background
            apply_property_review(cell, cell_pr, "cell", view)
            row["cells"].append(cell)
        return row

    @staticmethod
    def _end(block: Block) -> int:
        return int(block.get("pageEnd", block.get("page", 1)))

    @staticmethod
    def _cell_text(blocks: list[Block]) -> str:
        parts: list[str] = []
        for block in blocks:
            if block["type"] == "table":
                parts.extend(" | ".join(cell["text"] for cell in row["cells"]) for row in block["rows"])
            elif block["text"]:
                parts.append(block["text"])
        return "\n".join(parts)
