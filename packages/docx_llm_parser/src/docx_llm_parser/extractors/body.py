"""Parse the main body blocks of word/document.xml."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_TABLE,
    attr,
    child_elements,
    first_child,
    local_name,
)
from ..core.models import (
    AssetLookup,
    Block,
    BodyEvent,
    ContentControl,
    NumberingLabel,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
    append_warning,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.content_controls import parse_content_control
from ..ooxml.numbering import NumberingState
from ..ooxml.styles import StyleMap
from .inline import InlineParser


class BlockIdAllocator:
    """Assign stable internal IDs to body blocks."""

    def __init__(self) -> None:
        self._next = 1

    def allocate(self) -> str:
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
            on_bookmark=self._register_bookmark,
            on_comment_anchor=self._register_comment_anchor,
        )
        self.block_ids = BlockIdAllocator()
        self._order = 0
        self._table_index = 0
        self._page_hint = 1
        # Counter instead of boolean: a paragraph/table can contain multiple lastRenderedPageBreak elements.
        self._pending_page_breaks = 0
        self.body_events: list[BodyEvent] = []
        self._section_header_refs: list[tuple[str, str]] = []
        self._section_footer_refs: list[tuple[str, str]] = []
        self._comment_anchors: dict[str, str] = {}
        self._bookmarks_by_block: dict[str, list[str]] = {}
        self._section_index = 1
        self._section_break_pending = False

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
                    body_depth is not None and len(stack) == body_depth + 1 and len(stack) >= 2 and stack[-2] == "body"
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
                    self._section_break_pending = True
                    elem.clear()
                elif direct_body_child and lname == "sdt":
                    # Content controls wrap content (e.g. whole documents from
                    # template tools); parse their w:sdtContent children.
                    self._parse_sdt(elem, blocks)
                    elem.clear()
                elif direct_body_child and lname not in {
                    "bookmarkStart",
                    "bookmarkEnd",
                    "proofErr",
                    "permStart",
                    "permEnd",
                }:
                    # Content-bearing wrappers we do not support must not be
                    # dropped silently.
                    self._warn(
                        "UNSUPPORTED_BODY_CHILD",
                        f"Unsupported body-level element: {lname}",
                        part="word/document.xml",
                    )
                    elem.clear()

                if lname == "body":
                    body_depth = None
                stack.pop()
        self._discard_unreferenced_anchors(blocks)
        for parsed_block in blocks:
            self._add_body_event(parsed_block)
        if self._section_index == 1:
            # A lone default section has no navigation value; omit it from the IR
            # so all densities remain free of redundant section metadata.
            for parsed_block in blocks:
                cast(dict[str, object], parsed_block).pop("section", None)
        return blocks

    def _parse_sdt(
        self,
        sdt: ET.Element,
        blocks: list[Block],
        parent_controls: tuple[ContentControl, ...] = (),
    ) -> None:
        """Parse a content control while preserving its metadata on its blocks."""
        controls = (*parent_controls, parse_content_control(sdt))
        content = first_child(sdt, "w", "sdtContent")
        if content is None:
            return
        for child in content:
            child_tag = child.tag
            if child_tag == _TAG_W_PARAGRAPH:
                block = self.parse_paragraph(child, "word/document.xml", controls)
                if block is not None:
                    blocks.append(block)
            elif child_tag == _TAG_W_TABLE:
                blocks.extend(self.parse_table(child, "word/document.xml", controls))
            elif local_name(child_tag) == "sdt":
                self._parse_sdt(child, blocks, controls)

    def parse_paragraph(
        self,
        paragraph: ET.Element,
        part: str,
        content_controls: tuple[ContentControl, ...] = (),
    ) -> TextBlock | None:
        """Parse a paragraph; emit a heading only when the style outline level is explicit."""
        block_id = self.block_ids.allocate()
        self._order += 1
        section_index = self._begin_section()
        # Apply the page-break count accumulated by the previous block.
        page_start = self._flush_pending_page_breaks()

        style_id = self._paragraph_style_id(paragraph)
        paragraph_properties = first_child(paragraph, "w", "pPr")
        section_break = first_child(paragraph_properties, "w", "sectPr")
        if section_break is not None:
            # A sectPr in pPr ends the section after this paragraph; Word
            # renders the next content on a new page.
            self._collect_section_refs(section_break)
        runs, raw_hints = self.inline.paragraph_runs(paragraph, part, block_id, style_id)
        anchors = self._bookmarks_by_block.pop(block_id, [])
        numbering = self._paragraph_numbering(paragraph, style_id, part, block_id)
        if numbering is not None:
            # Auto-numbering is visible Word text; insert it into the text stream as a synthetic run.
            runs.insert(0, {"text": numbering["text"]})
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
            and not content_controls
            and not self.options.preserve_empty_paragraphs
        ):
            # Empty paragraphs (no visible text, no inline objects) produce no content.
            # lrpb/manual page breaks inside a paragraph have no visual effect in Word
            # rendering, so drop them without advancing the page number.
            self._pending_page_breaks = 0
            if section_break is not None:
                # Even an empty paragraph's sectPr still starts a new page in Word.
                self._pending_page_breaks = 1
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
                "section": section_index,
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
                "section": section_index,
            }
        if numbering is not None:
            block["numbering"] = numbering
        if content_controls:
            block["contentControls"] = list(content_controls)
        if anchors:
            block["anchors"] = anchors
        if self.options.include_runs:
            block["runs"] = runs
        if self.options.include_raw_hints and raw_hints:
            block["rawHints"] = raw_hints
        if section_break is not None:
            # The section break follows this paragraph; the next block starts
            # on a new page.
            self._pending_page_breaks += 1
            self._section_break_pending = True
        return block

    def _register_bookmark(self, name: str, block_id: str) -> None:
        """Register a bookmark while its enclosing paragraph still has a stable block ID."""
        anchors = self._bookmarks_by_block.setdefault(block_id, [])
        if name not in anchors:
            anchors.append(name)

    def _register_comment_anchor(self, comment_id: str, block_id: str) -> None:
        """Keep the first visible block for a Word comment range/reference."""
        self._comment_anchors.setdefault(comment_id, block_id)

    @staticmethod
    def _discard_unreferenced_anchors(blocks: list[Block]) -> None:
        """Avoid carrying bookmarks that are never a parsed internal-navigation target."""
        all_blocks: list[Block] = []

        def visit(items: list[Block]) -> None:
            for item in items:
                all_blocks.append(item)
                if item["type"] == "table":
                    for row in item["rows"]:
                        for cell in row["cells"]:
                            visit(cell["blocks"])

        visit(blocks)
        used = {
            link["anchor"]
            for item in all_blocks
            if item["type"] in {"paragraph", "heading"}
            for run in item.get("runs", [])
            if (link := run.get("link")) is not None and link.get("anchor")
        }
        for item in all_blocks:
            if item["type"] not in {"paragraph", "heading"}:
                continue
            anchors = [anchor for anchor in item.get("anchors", []) if anchor in used]
            if anchors:
                item["anchors"] = anchors
            else:
                cast(dict[str, object], item).pop("anchors", None)

    def parse_table(
        self,
        table: ET.Element,
        part: str,
        content_controls: tuple[ContentControl, ...] = (),
    ) -> list[TableBlock]:
        """Parse a Word table, preserving rows/columns, merged cells, and cell blocks.
        When a page break occurs inside the table, split it into multiple blocks so the
        renderer can emit <page n=N> between sub-tables.
        Multiple lrpb across cells in the same row collapse into a single page-break
        decision (based on _page_hint changes)."""
        self._order += 1
        section_index = self._begin_section()
        table_id = self._next_table_id()
        # Apply the page-break count accumulated by the previous block.
        segment_page = self._flush_pending_page_breaks()

        sub_tables: list[TableBlock] = []
        segment_rows: list[TableRow] = []
        merge_state: dict[int, TableCell] = {}
        widest_column_count = 0
        # Record the page number before processing this row, to tell whether the row triggered a page break.
        page_before_row = self._page_hint

        for row_index, row_element in enumerate(child_elements(table, "w", "tr")):
            row, row_width = self._parse_table_row(row_element, row_index, part)
            widest_column_count = max(widest_column_count, row_width)

            # Did _page_hint change after processing this row? Multiple lrpb in one row count as a single page break.
            if self._page_hint != page_before_row:
                if segment_rows:
                    self._apply_vertical_merges(segment_rows, merge_state)
                    sub_tables.append(
                        self._make_table_block(
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
                    segment_rows = []
                # Multiple lrpb across cells in the same row collapse into one page break: the page number only increments by 1.
                self._page_hint = page_before_row + 1
                self._pending_page_breaks = 0
                segment_page = self._page_hint

            segment_rows.append(row)
            page_before_row = self._page_hint

        # Commit the final batch of rows.
        if segment_rows:
            self._apply_vertical_merges(segment_rows, merge_state)
            sub_tables.append(
                self._make_table_block(
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

        return sub_tables

    def _make_table_block(
        self,
        part: str,
        page: int,
        rows: list[TableRow],
        max_col: int,
        table_id: str,
        segment_index: int,
        section_index: int,
        content_controls: tuple[ContentControl, ...] = (),
    ) -> TableBlock:
        """Build a table block dictionary."""
        block_id = self.block_ids.allocate()
        block: TableBlock = {
            "id": block_id,
            "type": "table",
            "part": part,
            "order": self._order,
            "page": page,
            "tableId": table_id,
            "segmentIndex": segment_index,
            "rows": rows,
            "columnCount": max_col,
            "section": section_index,
        }
        if content_controls:
            block["contentControls"] = list(content_controls)
        return block

    def _parse_table_row(self, row_element: ET.Element, row_index: int, part: str) -> tuple[TableRow, int]:
        """Parse one table row and return the row plus its visual column count."""
        cells: list[TableCell] = []
        next_column = 0
        is_header = first_child(first_child(row_element, "w", "trPr"), "w", "tblHeader") is not None
        for cell_element in child_elements(row_element, "w", "tc"):
            # A Word table is not a simple 2D array; colSpan/vMerge info must be recorded.
            col_span = self._cell_col_span(cell_element)
            vertical_merge = self._cell_v_merge(cell_element)
            cell_blocks = self._parse_cell_blocks(cell_element, part)
            cell: TableCell = {
                "rowIndex": row_index,
                "colIndex": next_column,
                "rowSpan": 1,
                "colSpan": col_span,
                "text": self._cell_text_from_blocks(cell_blocks),
                "blocks": cell_blocks,
            }
            if vertical_merge:
                cell["vMerge"] = vertical_merge
            cells.append(cell)
            next_column += col_span

        row: TableRow = {"rowIndex": row_index, "cells": cells}
        if is_header:
            # Repeated header rows help LLMs understand table semantics, so keep them as a lightweight flag.
            row["isHeader"] = True
        return row, next_column

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
            elif local_name(child_tag) == "sdt":
                self._parse_sdt(child, blocks)
        return blocks

    def _apply_vertical_merges(self, rows: list[TableRow], active: dict[int, TableCell] | None = None) -> None:
        """Add rowSpan to merge origins based on vMerge.

        *active* carries merge origins across page-separated table segments,
        so a restart in one segment keeps accumulating rowSpan in the next.
        """
        if active is None:
            active = {}
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

    def _paragraph_style_id(self, paragraph: ET.Element) -> str | None:
        """Read the paragraph style ID."""
        paragraph_properties = first_child(paragraph, "w", "pPr")
        pstyle = first_child(paragraph_properties, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _paragraph_numbering(
        self, paragraph: ET.Element, style_id: str | None, part: str, block_id: str
    ) -> NumberingLabel | None:
        """Read the paragraph numbering and advance the numbering counter."""
        paragraph_properties = first_child(paragraph, "w", "pPr")
        numbering_properties = first_child(paragraph_properties, "w", "numPr")
        style_numbering = self.styles.resolve_numbering(style_id)
        direct_num_id, direct_numbering_level = self._num_pr_values(numbering_properties)

        if direct_num_id == "0":
            # numId=0 means numbering is off in Word; it also doesn't fall back to the style's numbering.
            return None
        num_id = direct_num_id or (style_numbering[0] if style_numbering else None)
        if num_id is None:
            return None
        level = direct_numbering_level if direct_numbering_level is not None else (style_numbering[1] if style_numbering else 0)
        return self.numbering_state.advance(num_id, level, part=part, block_id=block_id)

    def _num_pr_values(self, numbering_properties: ET.Element | None) -> tuple[str | None, int | None]:
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

    def _cell_text_from_blocks(self, blocks: list[Block]) -> str:
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

    def _begin_section(self) -> int:
        """Advance at the first content block after a Word section break."""
        if self._section_break_pending:
            self._section_index += 1
            self._section_break_pending = False
        return self._section_index

    @property
    def section_refs(self) -> dict[str, list[tuple[str, str]]]:
        """Return the collected section references so AncillaryParser can filter unused headers/footers."""
        return {
            "headers": list(self._section_header_refs),
            "footers": list(self._section_footer_refs),
        }

    @property
    def comment_anchors(self) -> dict[str, str]:
        """Return comment ID to first visible body-block mapping for supplemental comments."""
        return dict(self._comment_anchors)

    def _warn(
        self,
        code: str,
        message: str,
        part: str | None = None,
        block_id: str | None = None,
    ) -> None:
        """Append a parse warning."""
        append_warning(self.warnings, code, message, part=part, block_id=block_id)
