"""Parse the main body blocks of word/document.xml."""

from __future__ import annotations

from typing import Any, cast
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_TABLE,
    attr,
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
    Run,
    TableBlock,
    TextBlock,
    append_warning,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.content_controls import parse_content_control
from ..ooxml.formatting import (
    merge_paragraph_borders,
    parse_paragraph_alignment,
    parse_paragraph_borders,
)
from ..ooxml.numbering import NumberingState, parse_numbering_change
from ..ooxml.styles import StyleMap
from .inline import InlineParser
from .table_parser import TableParser


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
        self.asset_lookup = asset_lookup
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
        self._table_parser = TableParser(self)

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
        alignment = parse_paragraph_alignment(paragraph_properties) or self.styles.resolve_paragraph_alignment(style_id)
        borders = merge_paragraph_borders(
            self.styles.resolve_paragraph_borders(style_id),
            parse_paragraph_borders(paragraph_properties),
        )
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
            marker_format = dict(numbering["markerFormat"])
            numbering_run: Run = {"text": numbering["text"]}
            if numbering["pictureBulletId"]:
                relationship_id = self.numbering_state.numbering.picture_bullet_relationship(numbering["pictureBulletId"])
                asset = self.asset_lookup.get(("word/numbering.xml", relationship_id or ""))
                if asset is not None:
                    numbering["markerImageId"] = asset["id"]
                    numbering_run = cast(
                        Run,
                        {
                            "text": " ",
                            "objects": [{"type": "image", "assetId": asset["id"], "alt": "Picture bullet"}],
                        },
                    )
            if marker_format:
                numbering_run["format"] = marker_format
            runs.insert(0, numbering_run)
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

        manual_page_breaks = sum(1 for hint in raw_hints if hint.get("type") == "manualPageBreak")
        # Explicit manual page breaks retain the parser's historical behavior:
        # the paragraph is assigned to the page after the break. Calculated Word
        # breaks are different: their inline position is preserved by sentinels.
        page_start += manual_page_breaks
        inline_page_breaks = sum(1 for run in runs if run.get("pageBreak"))
        leading_page_breaks = 0
        for run in runs:
            if run.get("pageBreak"):
                leading_page_breaks += 1
                continue
            if run["text"] or run.get("objects"):
                break
        content_page = page_start + leading_page_breaks
        # Updating the shared hint immediately also lets table parsing split before
        # the next row containing a calculated page break.
        self._page_hint = page_start + inline_page_breaks
        self._pending_page_breaks = 0

        heading_level = self.styles.resolve_heading_level(style_id)
        if heading_level is not None:
            # Headings come only from styles.xml / outlineLvl, never guessed from text shape.
            block: TextBlock = {
                "id": block_id,
                "type": "heading",
                "part": part,
                "order": self._order,
                "page": content_page,
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
                "page": content_page,
                "styleId": style_id,
                "text": text,
                "section": section_index,
            }
        if inline_page_breaks:
            block["pageEnd"] = page_start + inline_page_breaks
            if not self.options.include_runs:
                page_segments: list[dict[str, object]] = []
                segment_text: list[str] = []
                segment_page = page_start
                for run in runs:
                    if run.get("pageBreak"):
                        page_segments.append({"page": segment_page, "text": "".join(segment_text)})
                        segment_text = []
                        segment_page += 1
                    else:
                        segment_text.append(run["text"])
                page_segments.append({"page": segment_page, "text": "".join(segment_text)})
                block["pageSegments"] = page_segments
        if numbering is not None:
            block["numbering"] = numbering
        if alignment and alignment != "left":
            block["alignment"] = alignment
        if borders:
            block["borders"] = borders
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
        """Delegate table structure and table-local pagination to TableParser."""
        return self._table_parser.parse(table, part, content_controls)

    def _apply_vertical_merges(self, rows: list[Any], active: dict[int, Any] | None = None) -> None:
        """Compatibility delegate for callers that inspect table merge state."""
        self._table_parser.apply_vertical_merges(rows, active)


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
        level = direct_numbering_level
        if level is None:
            if style_numbering:
                level = self.numbering_state.numbering.level_for_style(style_numbering[0], style_id or "")
                if level is None:
                    level = style_numbering[1]
            else:
                level = 0

        previous_levels = None
        if self.options.revision_mode == "original":
            numbering_change = first_child(paragraph_properties, "w", "numberingChange")
            original = attr(numbering_change, "w", "original") if numbering_change is not None else None
            previous_levels = parse_numbering_change(original, self.warnings, part=part, block_id=block_id)
            if not previous_levels:
                previous_levels = None
        return self.numbering_state.advance(
            num_id,
            level,
            part=part,
            block_id=block_id,
            level_overrides=previous_levels,
        )

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
