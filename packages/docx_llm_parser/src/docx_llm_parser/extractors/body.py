"""Parse the main body blocks of word/document.xml."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_TABLE,
    attr,
    child_elements,
    first_child,
    local_name,
)
from ..core.locator import part_block_locator as locator
from ..core.models import (
    AssetLookup,
    Block,
    BodyEvent,
    NumberingLabel,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.numbering import NumberingState
from ..ooxml.styles import StyleMap
from .inline import InlineParser


class BlockIdAllocator:
    """Assign stable internal IDs to body blocks."""

    def __init__(self) -> None:
        self._next = 1

    def next(self) -> str:
        # Count independently per document to avoid shared state across concurrent parses.
        block_id = f"b{self._next}"
        self._next += 1
        return block_id


class DocumentBodyParser:
    """Parse the direct body content of document.xml into paragraphs, headings, and tables."""

    def __init__(
        self,
        package: PackageReader,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        numbering_state: NumberingState,
    ) -> None:
        self.package = package
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.numbering_state = numbering_state
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            on_page_break=self._mark_page_break,
        )
        self.ids = BlockIdAllocator()
        self._order = 0
        self._table_index = 0
        self._page_hint = 1
        # Counter instead of boolean: a paragraph/table can contain multiple lastRenderedPageBreak elements.
        self._pending_page_breaks = 0
        self.body_events: list[BodyEvent] = []
        self._section_header_refs: list[tuple[str, str]] = []
        self._section_footer_refs: list[tuple[str, str]] = []

    def parse(self) -> list[Block]:
        """Stream-parse word/document.xml, preserving the original paragraph/table order."""
        blocks: list[Block] = []
        with self.package.open_entry("word/document.xml") as stream:
            parser = ET.iterparse(stream, events=("start", "end"))
            stack: list[str] = []
            body_depth: int | None = None
            for event, elem in parser:
                # Optimization: use local_name to avoid split memory allocation.
                lname = local_name(elem.tag)
                if event == "start":
                    # start events only maintain the position stack; they don't build a full DOM.
                    stack.append(lname)
                    if lname == "body":
                        body_depth = len(stack)
                    continue

                direct_body_child = (
                    body_depth is not None
                    and len(stack) == body_depth + 1
                    and len(stack) >= 2
                    and stack[-2] == "body"
                )
                if direct_body_child and lname == "p":
                    # Only handle paragraphs that are direct children of body, so table cell content is not hoisted twice.
                    block = self.parse_paragraph(elem, "word/document.xml")
                    if block is not None:
                        blocks.append(block)
                    elem.clear()
                elif direct_body_child and lname == "tbl":
                    # Tables can contain page breaks, so parse_table returns a list (one sub-table block per page).
                    blocks.extend(self.parse_table(elem, "word/document.xml"))
                    elem.clear()
                elif direct_body_child and lname == "sectPr":
                    # Section break: Word always starts a new section on a new page when rendering.
                    self._collect_section_refs(elem)
                    self._pending_page_breaks += 1
                    elem.clear()

                if lname == "body":
                    body_depth = None
                stack.pop()
        for parsed_block in blocks:
            self._add_body_event(parsed_block)
        return blocks

    def parse_paragraph(self, p: ET.Element, part: str) -> TextBlock | None:
        """Parse a paragraph; emit a heading only when the style outline level is explicit."""
        block_id = self.ids.next()
        self._order += 1
        # Apply the page-break count accumulated by the previous block.
        page_start = self._flush_pending_page_breaks()

        style_id = self._paragraph_style_id(p)
        runs, raw_hints = self.inline.paragraph_runs(p, part, block_id, style_id)
        numbering = self._paragraph_numbering(p, style_id, part, block_id)
        if numbering is not None:
            # Auto-numbering is visible Word text; insert it into the text stream as a synthetic run.
            runs.insert(0, {"text": numbering["text"], "kind": "numberingLabel"})
            raw_hints.append({"type": "numbering", **numbering})

        # Collect text and detect inline objects in a single pass to avoid double iteration on the hot path.
        text_parts: list[str] = []
        has_objects = False
        for run in runs:
            text_parts.append(run["text"])
            if "objects" in run:
                has_objects = True
        text = "".join(text_parts)
        # text.isspace() avoids the cost of text.strip() creating a new string.
        if (
            (not text or text.isspace())
            and not has_objects
            and not self.options.preserve_empty_paragraphs
        ):
            # Empty paragraphs (no visible text, no inline objects) produce no content.
            # lrpb/manual page breaks inside a paragraph have no visual effect in Word
            # rendering, so drop them without advancing the page number.
            self._pending_page_breaks = 0
            return None

        # lrpb/manual page breaks inside the paragraph advance this paragraph's starting page number.
        page_start += self._pending_page_breaks
        self._page_hint = page_start
        self._pending_page_breaks = 0

        heading_level = self.styles.resolve_heading_level(style_id)
        if heading_level is not None:
            # Headings come only from styles.xml / outlineLvl, never guessed from text shape.
            block: TextBlock = {
                "id": block_id,
                "type": "heading",
                "part": part,
                "order": self._order,
                "page": page_start,
                "styleId": style_id,
                "text": text,
                "level": heading_level,
                "headingSource": "style",
            }
        else:
            block = {
                "id": block_id,
                "type": "paragraph",
                "part": part,
                "order": self._order,
                "page": page_start,
                "styleId": style_id,
                "text": text,
            }
        if numbering is not None:
            block["numbering"] = numbering
        if self.options.include_runs:
            block["runs"] = runs
        if self.options.include_raw_hints and raw_hints:
            block["rawHints"] = raw_hints
        return block

    def parse_table(self, tbl: ET.Element, part: str) -> list[TableBlock]:
        """Parse a Word table, preserving rows/columns, merged cells, and cell blocks.
        When a page break occurs inside the table, split it into multiple blocks so the
        renderer can emit <page n=N> between sub-tables.
        Multiple lrpb across cells in the same row collapse into a single page-break
        decision (based on _page_hint changes)."""
        self._order += 1
        table_id = self._next_table_id()
        # Apply the page-break count accumulated by the previous block.
        current_page = self._flush_pending_page_breaks()

        sub_tables: list[TableBlock] = []
        current_rows: list[TableRow] = []
        max_col = 0
        # Record the page number before processing this row, to tell whether the row triggered a page break.
        page_before_row = self._page_hint

        for row_index, tr in enumerate(child_elements(tbl, "w", "tr")):
            cells: list[TableCell] = []
            col_index = 0
            is_header = first_child(first_child(tr, "w", "trPr"), "w", "tblHeader") is not None
            for tc in child_elements(tr, "w", "tc"):
                # A Word table is not a simple 2D array; colSpan/vMerge info must be recorded.
                col_span = self._cell_col_span(tc)
                v_merge = self._cell_v_merge(tc)
                cell_blocks = self._parse_cell_blocks(tc, part)
                text = self._blocks_text(cell_blocks)
                cell: TableCell = {
                    "rowIndex": row_index,
                    "colIndex": col_index,
                    "rowSpan": 1,
                    "colSpan": col_span,
                    "text": text,
                    "blocks": cell_blocks,
                }
                if v_merge:
                    cell["vMerge"] = v_merge
                cells.append(cell)
                col_index += col_span
            max_col = max(max_col, col_index)
            row: TableRow = {"rowIndex": row_index, "cells": cells}
            if is_header:
                # Repeated header rows help LLMs understand table semantics, so keep them as a lightweight flag.
                row["isHeader"] = True

            # Did _page_hint change after processing this row? Multiple lrpb in one row count as a single page break.
            if self._page_hint != page_before_row:
                if current_rows:
                    sub_tables.append(
                        self._make_table_block(
                            part,
                            current_page,
                            current_rows,
                            max_col,
                            table_id,
                            len(sub_tables) + 1,
                        )
                    )
                    current_rows = []
                # Multiple lrpb across cells in the same row collapse into one page break: the page number only increments by 1.
                self._page_hint = page_before_row + 1
                self._pending_page_breaks = 0
                current_page = self._page_hint

            current_rows.append(row)
            page_before_row = self._page_hint

        # Commit the final batch of rows.
        if current_rows:
            self._apply_vertical_merges(current_rows)
            sub_tables.append(
                self._make_table_block(
                    part,
                    current_page,
                    current_rows,
                    max_col,
                    table_id,
                    len(sub_tables) + 1,
                )
            )

        return sub_tables

    def _make_table_block(
        self,
        part: str,
        page: int,
        rows: list[TableRow],
        max_col: int,
        table_id: str,
        segment_index: int,
    ) -> TableBlock:
        """Build a table block dictionary."""
        block_id = self.ids.next()
        return {
            "id": block_id,
            "type": "table",
            "part": part,
            "order": self._order,
            "page": page,
            "tableId": table_id,
            "segmentIndex": segment_index,
            "rows": rows,
            "columnCount": max_col,
        }

    def _next_table_id(self) -> str:
        """Allocate a stable document-order ID for one logical table."""
        self._table_index += 1
        return f"t{self._table_index}"

    def _parse_cell_blocks(self, tc: ET.Element, part: str) -> list[Block]:
        """Parse cell content; cells can contain paragraphs and nested tables.
        Optimization: compare against precomputed tag names to avoid a local_name call per child."""
        blocks: list[Block] = []
        for child in tc:
            child_tag = child.tag
            if child_tag == _TAG_W_PARAGRAPH:
                # Cell paragraphs are kept as nested blocks to avoid losing multi-paragraph structure.
                block = self.parse_paragraph(child, part)
                if block is not None:
                    blocks.append(block)
            elif child_tag == _TAG_W_TABLE:
                # Nested tables are parsed recursively; page breaks inside them also split into sub-tables.
                blocks.extend(self.parse_table(child, part))
        return blocks

    def _apply_vertical_merges(self, rows: list[TableRow]) -> None:
        """Add rowSpan to merge origins based on vMerge."""
        active: dict[int, TableCell] = {}
        for row in rows:
            for cell in row["cells"]:
                columns = range(cell["colIndex"], cell["colIndex"] + cell["colSpan"])
                v_merge = cell.get("vMerge")
                if v_merge == "restart":
                    # A restart cell becomes the vertical merge origin for subsequent continue cells.
                    for column in columns:
                        active[column] = cell
                elif v_merge == "continue":
                    # A continue cell advances the origin's rowSpan while keeping its own position for grid reconstruction.
                    origins: list[TableCell] = []
                    for column in columns:
                        origin = active.get(column)
                        if origin is not None and origin not in origins:
                            origins.append(origin)
                    for origin in origins:
                        origin["rowSpan"] += 1
                else:
                    # A non-merged cell truncates the previous active merge in the same column.
                    for column in columns:
                        active.pop(column, None)

    def _paragraph_style_id(self, p: ET.Element) -> str | None:
        """Read the paragraph style ID."""
        paragraph_properties = first_child(p, "w", "pPr")
        pstyle = first_child(paragraph_properties, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _paragraph_numbering(
        self, p: ET.Element, style_id: str | None, part: str, block_id: str
    ) -> NumberingLabel | None:
        """Read the paragraph numbering and advance the numbering counter."""
        paragraph_properties = first_child(p, "w", "pPr")
        numbering_properties = first_child(paragraph_properties, "w", "numPr")
        style_numbering = self.styles.resolve_numbering(style_id)
        direct_num_id, direct_level = self._num_pr_values(numbering_properties)

        if direct_num_id == "0":
            # numId=0 means numbering is off in Word; it also doesn't fall back to the style's numbering.
            return None
        num_id = direct_num_id or (style_numbering[0] if style_numbering else None)
        if num_id is None:
            return None
        level = (
            direct_level
            if direct_level is not None
            else (style_numbering[1] if style_numbering else 0)
        )
        return self.numbering_state.advance(num_id, level, part=part, block_id=block_id)

    def _num_pr_values(
        self, numbering_properties: ET.Element | None
    ) -> tuple[str | None, int | None]:
        """Read numId and ilvl from w:numPr."""
        if numbering_properties is None:
            return (None, None)
        num_id_node = first_child(numbering_properties, "w", "numId")
        ilvl_node = first_child(numbering_properties, "w", "ilvl")
        num_id = attr(num_id_node, "w", "val") if num_id_node is not None else None
        level_str = attr(ilvl_node, "w", "val") if ilvl_node is not None else None
        if level_str is None:
            return (num_id, None)
        try:
            return (num_id, int(level_str))
        except ValueError:
            # An invalid level must not abort parsing; treat it as level 0 and record a warning.
            self._warn(
                "INVALID_PARAGRAPH_NUMBERING_LEVEL",
                f"Invalid paragraph numbering level: {level_str!r}",
                part="word/document.xml",
            )
            return (num_id, 0)

    def _cell_col_span(self, tc: ET.Element) -> int:
        """Read the horizontal merge column count."""
        tcpr = first_child(tc, "w", "tcPr")
        grid_span = first_child(tcpr, "w", "gridSpan")
        val = attr(grid_span, "w", "val") if grid_span is not None else None
        if val is None:
            return 1
        try:
            return max(1, int(val))
        except ValueError:
            # An invalid gridSpan must not abort parsing of the whole document.
            self._warn(
                "INVALID_GRID_SPAN",
                f"Invalid gridSpan value: {val!r}",
                part="word/document.xml",
            )
            return 1

    def _cell_v_merge(self, tc: ET.Element) -> str | None:
        """Read the vertical merge marker."""
        tcpr = first_child(tc, "w", "tcPr")
        vmerge = first_child(tcpr, "w", "vMerge")
        if vmerge is None:
            return None
        return attr(vmerge, "w", "val") or "continue"

    def _blocks_text(self, blocks: list[Block]) -> str:
        """Combine the cell's nested blocks into human-readable cell text."""
        parts: list[str] = []
        for block in blocks:
            if block["type"] in {"paragraph", "heading"}:
                if block["text"]:
                    parts.append(block["text"])
            elif block["type"] == "table":
                for row in block["rows"]:
                    cell_text = " | ".join(cell["text"] for cell in row["cells"])
                    if cell_text.strip():
                        parts.append(cell_text)
        return "\n".join(parts)

    def _add_body_event(self, block: Block) -> None:
        """Record a body event for debugging; it does not affect the final LLM output."""
        event: BodyEvent = {
            "id": block["id"],
            "type": block["type"],
            "order": block["order"],
            "part": block["part"],
        }
        if block["type"] in {"paragraph", "heading"}:
            event["textPreview"] = block["text"][:120]
            if "numbering" in block:
                event["numberingLabel"] = block["numbering"]["label"]
        if block["type"] == "heading":
            event["level"] = block["level"]
        if block["type"] == "table":
            event["rowCount"] = len(block["rows"])
            event["columnCount"] = block["columnCount"]
        self.body_events.append(event)

    def _mark_page_break(self) -> None:
        """Called by InlineParser when an lrpb/manual page break is found; increments the pending page-break count."""
        self._pending_page_breaks += 1

    def _flush_pending_page_breaks(self) -> int:
        """Apply accumulated page breaks and return the current page number."""
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0
        return self._page_hint

    def _collect_section_refs(self, sect_pr: ET.Element) -> None:
        """Extract header/footer references from sectPr."""
        for child in sect_pr:
            lname = local_name(child.tag)
            r_id = attr(child, "r", "id")
            if not r_id:
                continue
            ref_type = attr(child, "w", "type") or "default"
            if lname == "headerReference":
                self._section_header_refs.append((r_id, ref_type))
            elif lname == "footerReference":
                self._section_footer_refs.append((r_id, ref_type))

    @property
    def section_refs(self) -> dict[str, list[tuple[str, str]]]:
        """Return the collected section references so AncillaryParser can filter unused headers/footers."""
        return {
            "headers": list(self._section_header_refs),
            "footers": list(self._section_footer_refs),
        }

    def _warn(
        self,
        code: str,
        message: str,
        part: str | None = None,
        block_id: str | None = None,
    ) -> None:
        """Append a parse warning."""
        self.warnings.append(
            ParseWarning(
                code=code,
                message=message,
                locator=locator(part, block_id),
            )
        )
