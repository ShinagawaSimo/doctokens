"""Parse the main body blocks of word/document.xml."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex

from ....model import (
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
from ....ooxml.compatibility import DocxCompatibility
from ....ooxml.formatting import (
    merge_paragraph_borders,
    parse_paragraph_alignment,
    parse_paragraph_borders,
    visible_run_format,
)
from ....ooxml.namespaces import first_child
from ....ooxml.numbering import NumberingState
from ....ooxml.outline import parse_outline_level
from ....ooxml.package import PackageReader
from ....ooxml.property_changes import (
    property_change,
    reading_properties,
    revision_record,
    selected_properties,
    structural_revision,
)
from ....ooxml.styles import StyleMap
from ...plan import DocxFeature, DocxParsePlan
from .anchors import BlockIdAllocator, BodyAnchors
from .inline import InlineParser
from .numbering import ParagraphNumbering, _paragraph_style_id
from .paragraph_groups import ParagraphPart
from .sections import BodySections
from .stream import read_blocks
from .tables import TableParser
from .textboxes import parse_textbox_blocks


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
        compatibility: DocxCompatibility | None = None,
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
        self.compatibility = compatibility or DocxCompatibility(warnings, asset_lookup)
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
        self.table_ids = BlockIdAllocator("t")
        self._page_hint = 1
        # Counter instead of boolean: a paragraph/table can contain multiple lastRenderedPageBreak elements.
        self._pending_page_breaks = 0
        self._table_parser = TableParser(self)
        self._textbox_depth = 0
        self.inline.textbox_reader = lambda node, part: parse_textbox_blocks(self, node, part)

    def parse(self) -> list[Block]:
        """Stream-parse word/document.xml, preserving the original paragraph/table order."""
        blocks = read_blocks(self)
        if self._sections._section_index == 1:
            # A lone default section has no navigation value; omit it from the IR
            # so all densities remain free of redundant section metadata.
            for parsed_block in blocks:
                cast(dict[str, object], parsed_block).pop("section", None)
        return blocks

    def parse_paragraph(
        self,
        paragraph: ET.Element,
        part: str,
        content_controls: tuple[ContentControl, ...] = (),
        *,
        paragraph_parts: list[ParagraphPart] | None = None,
    ) -> TextBlock | None:
        """Parse a paragraph using its explicit outline level before its style."""
        block_id = self.block_ids.allocate()
        self._order += 1
        section_index = self._sections._begin_section()
        # Apply the page-break count accumulated by the previous block.
        page_start = self._flush_pending_page_breaks()

        style_id = self.styles.style_id(_paragraph_style_id(paragraph, str(self.options.revision_mode)), "paragraph")
        current_properties = first_child(paragraph, "w", "pPr")
        paragraph_properties = selected_properties(current_properties, str(self.options.revision_mode))
        table_style = (
            self.inline.table_style_for_paragraph(paragraph_properties)
            if self.inline.table_style_for_paragraph
            else self.inline.table_style
        )
        inherited = self.styles.paragraph(style_id, table_style)
        alignment = None
        borders = {}
        if self.include_character_formatting:
            alignment = parse_paragraph_alignment(paragraph_properties) or inherited.alignment
            borders = merge_paragraph_borders(
                inherited.borders,
                parse_paragraph_borders(paragraph_properties),
            )
            borders = {side: border for side, border in borders.items() if border.get("style") not in {"nil", "none"}}
        section_break = first_child(paragraph_properties, "w", "sectPr")
        if section_break is not None:
            # A sectPr in pPr ends the section after this paragraph; Word
            # renders the next content on a new page.
            self._sections._collect_section_refs(section_break)
        runs, raw_hints = self.inline.paragraph_runs(paragraph, part, block_id, style_id, paragraph_parts, content_controls)
        anchors = self._anchors._bookmarks_by_block.pop(block_id, [])
        numbering = self._numbering.parse(paragraph, style_id, part, block_id, inherited)
        if numbering is not None:
            # Auto-numbering is visible Word text; insert it into the text stream as a synthetic run.
            marker_format = visible_run_format(numbering["markerFormat"]) if self.include_character_formatting else {}
            numbering_run: Run = {"text": numbering["text"]}
            if self._numbering.last_change:
                numbering_run["propertyChanges"] = [self._numbering.last_change]
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
            if "objects" in run or "ruby" in run:
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
            if run["text"] or run.get("objects") or run.get("ruby"):
                break
        content_page = page_start + leading_page_breaks
        # Updating the shared hint immediately also lets table parsing split before
        # the next row containing a calculated page break.
        self._page_hint = page_start + inline_page_breaks
        self._pending_page_breaks = 0

        outline_level = parse_outline_level(paragraph_properties, self.warnings, part=part, block_id=block_id)
        effective_outline = inherited.outline_level if outline_level is None else outline_level
        heading_level = effective_outline + 1 if effective_outline is not None and effective_outline < 9 else None
        if heading_level is not None:
            # Headings come only from explicit outlineLvl, never guessed from text shape.
            block: TextBlock = {
                "id": block_id,
                "type": "heading",
                "part": part,
                "order": self._order,
                "page": content_page,
                "styleId": style_id,
                "text": text,
                "level": heading_level,
                "headingSource": "paragraph" if outline_level is not None else "style",
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
        if self.options.revision_mode == "review":
            mark = structural_revision(first_child(current_properties, "w", "rPr"))
            if mark is not None:
                block["paragraphMark"] = revision_record(mark)
            change = property_change(
                current_properties,
                "paragraph",
                reading_properties(selected_properties(current_properties, "original")),
                reading_properties(current_properties),
            )
            if change:
                block["propertyChanges"] = [change]
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
