"""Parse the main body blocks of word/document.xml."""

from __future__ import annotations

from typing import Any, cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.xml import iterparse

from ....core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_TABLE,
    first_child,
    local_name,
)
from ....core.models import (
    AssetLookup,
    Block,
    ContentControl,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    Run,
    TableBlock,
    TextBlock,
    append_warning,
)
from ....core.package import PackageReader
from ....core.relationships import RelationshipIndex
from ....ooxml.content_controls import parse_content_control
from ....ooxml.formatting import (
    merge_paragraph_borders,
    parse_paragraph_alignment,
    parse_paragraph_borders,
)
from ....ooxml.numbering import NumberingState
from ....ooxml.styles import StyleMap
from ....plan import DocxFeature, DocxParsePlan
from .anchors import BlockIdAllocator, BodyAnchors
from .inline import InlineParser
from .numbering import ParagraphNumbering, _paragraph_style_id
from .sections import BodySections
from .tables import TableParser


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
        plan: DocxParsePlan | None = None,
    ) -> None:
        self.package = package
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.numbering_state = numbering_state
        self._numbering = ParagraphNumbering(styles, numbering_state, options, warnings)
        self.plan = plan or DocxParsePlan.session()
        # These booleans are stable for the whole parse.  Resolving the Flag
        # once avoids repeated bit operations in the document hot loop.
        self.include_character_formatting = self.plan.needs(DocxFeature.CHARACTER_FORMATTING)
        self.include_raw_hints = self.plan.needs(DocxFeature.RAW_HINTS)
        self.asset_lookup = asset_lookup
        self._anchors = BodyAnchors()
        self._sections = BodySections()
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            plan=self.plan,
            on_page_break=self._mark_page_break,
            on_bookmark=self._anchors._register_bookmark,
            on_comment_anchor=self._anchors._register_comment_anchor,
        )
        self.block_ids = BlockIdAllocator()
        self._order = 0
        self._table_index = 0
        self._page_hint = 1
        # Counter instead of boolean: a paragraph/table can contain multiple lastRenderedPageBreak elements.
        self._pending_page_breaks = 0
        self._table_parser = TableParser(self)

    def parse(self) -> list[Block]:
        """Stream-parse word/document.xml, preserving the original paragraph/table order."""
        blocks: list[Block] = []
        with self.package.open_entry("word/document.xml") as stream:
            parser = iterparse(stream, events=("start", "end"))
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
                    self._sections._collect_section_refs(elem)
                    self._pending_page_breaks += 1
                    self._sections._section_break_pending = True
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
        self._anchors._discard_unreferenced_anchors(blocks)
        if self._sections._section_index == 1:
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
        section_index = self._sections._begin_section()
        # Apply the page-break count accumulated by the previous block.
        page_start = self._flush_pending_page_breaks()

        style_id = _paragraph_style_id(paragraph)
        paragraph_properties = first_child(paragraph, "w", "pPr")
        alignment = None
        borders = {}
        if self.include_character_formatting:
            alignment = parse_paragraph_alignment(paragraph_properties) or self.styles.resolve_paragraph_alignment(style_id)
            borders = merge_paragraph_borders(
                self.styles.resolve_paragraph_borders(style_id),
                parse_paragraph_borders(paragraph_properties),
            )
        section_break = first_child(paragraph_properties, "w", "sectPr")
        if section_break is not None:
            # A sectPr in pPr ends the section after this paragraph; Word
            # renders the next content on a new page.
            self._sections._collect_section_refs(section_break)
        runs, raw_hints = self.inline.paragraph_runs(paragraph, part, block_id, style_id)
        anchors = self._anchors._bookmarks_by_block.pop(block_id, [])
        numbering = self._numbering.parse(paragraph, style_id, part, block_id)
        if numbering is not None:
            # Auto-numbering is visible Word text; insert it into the text stream as a synthetic run.
            marker_format = dict(numbering["markerFormat"]) if self.include_character_formatting else {}
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
            if self.include_raw_hints:
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
        if self.include_raw_hints and self.options.include_raw_hints and raw_hints:
            block["rawHints"] = raw_hints
        if section_break is not None:
            # The section break follows this paragraph; the next block starts
            # on a new page.
            self._pending_page_breaks += 1
            self._sections._section_break_pending = True
        return block

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

    def _mark_page_break(self) -> None:
        """Called by InlineParser when an lrpb/manual page break is found; increments the pending page-break count."""
        self._pending_page_breaks += 1

    def _flush_pending_page_breaks(self) -> int:
        """Apply accumulated page breaks and return the current page number."""
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0
        return self._page_hint

    @property
    def section_refs(self) -> dict[str, list[tuple[str, str]]]:
        """Return the headers and footers referenced by parsed body sections."""
        return self._sections.section_refs

    @property
    def comment_anchors(self) -> dict[str, str]:
        """Return comment ID to first visible body-block mapping for supplemental comments."""
        return dict(self._anchors._comment_anchors)

    def _warn(
        self,
        code: str,
        message: str,
        part: str | None = None,
        block_id: str | None = None,
    ) -> None:
        """Append a parse warning."""
        append_warning(self.warnings, code, message, part=part, block_id=block_id)
