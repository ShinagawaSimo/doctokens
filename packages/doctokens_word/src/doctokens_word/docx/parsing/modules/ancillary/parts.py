"""Extract ancillary content: headers, footers, footnotes, endnotes, and comments."""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_core.containers.opc.xml import local_attr

from ....model import (
    AncillaryContent,
    AncillaryItem,
    AncillaryResult,
    AssetLookup,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    append_warning,
)
from ....ooxml.compatibility import DocxCompatibility
from ....ooxml.namespaces import attr, child_elements, local_name
from ....ooxml.package import PackageReader
from ....ooxml.styles import StyleMap
from ...plan import DocxFeature, DocxParsePlan
from ..body.inline import InlineParser
from ..body.textboxes import TextboxReader
from .content import AncillaryContentParser, has_objects


class AncillaryParser:
    """Extract content outside the body that is still valuable for LLM understanding."""

    def __init__(
        self,
        package: PackageReader,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        comment_anchors: Mapping[str, str] | None = None,
        plan: DocxParsePlan | None = None,
        compatibility: DocxCompatibility | None = None,
        textbox_reader: TextboxReader | None = None,
    ) -> None:
        self.package = package
        self.options = options
        self.plan = plan or DocxParsePlan.session()
        self.warnings = warnings
        self.compatibility = compatibility or DocxCompatibility(warnings, asset_lookup)
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            plan=self.plan,
        )
        self.inline.textbox_reader = textbox_reader
        self._block_index = 0
        self.content = AncillaryContentParser(self.inline, self._next_block_id)
        self._comment_anchors = dict(comment_anchors or {})

    def parse(self) -> AncillaryResult:
        """Return five categories of ancillary content."""
        return {
            "headers": self._parse_header_footer("header") if self.plan.needs(DocxFeature.HEADERS) else [],
            "footers": self._parse_header_footer("footer") if self.plan.needs(DocxFeature.FOOTERS) else [],
            "footnotes": self._parse_notes("word/footnotes.xml", "footnote") if self.plan.needs(DocxFeature.FOOTNOTES) else [],
            "endnotes": self._parse_notes("word/endnotes.xml", "endnote") if self.plan.needs(DocxFeature.ENDNOTES) else [],
            "comments": self._parse_comments() if self.plan.needs(DocxFeature.COMMENTS) else [],
        }

    # ── per-part-type drivers ─────────────────────────────────────

    def _parse_header_footer(self, kind: str) -> list[AncillaryItem]:
        """Parse word/header*.xml or word/footer*.xml."""
        prefix = f"word/{kind}"
        rows: list[AncillaryItem] = []
        for name in sorted(item["name"] for item in self.package.read_entry_index()):
            if not (name.startswith(prefix) and name.endswith(".xml")):
                continue
            root = self._parse_xml_part(name)
            if root is None:
                continue
            self.inline.revisions.ranges.clear()
            content = self.content.read(root, name)
            item_id = name.rsplit("/", 1)[-1].removesuffix(".xml")
            self._try_emit_item(item_id, f"{kind}s.{item_id}", content, rows)
        return rows

    def _parse_notes(self, part_name: str, tag_name: str) -> list[AncillaryItem]:
        """Parse footnotes or endnotes."""
        if not self.package.exists(part_name):
            return []
        root = self._parse_xml_part(part_name)
        if root is None:
            return []
        rows: list[AncillaryItem] = []
        group = "footnotes" if tag_name == "footnote" else "endnotes"
        for note in child_elements(root, "w", tag_name):
            note_type = attr(note, "w", "type")
            if note_type in {"separator", "continuationSeparator"}:
                continue
            note_id = attr(note, "w", "id")
            if not note_id:
                continue
            self.inline.revisions.ranges.clear()
            content = self.content.read(note, part_name)
            self._try_emit_item(note_id, f"{group}.{note_id}", content, rows)
        return rows

    def _parse_comments(self) -> list[AncillaryItem]:
        """Parse comment text."""
        part_name = "word/comments.xml"
        if not self.package.exists(part_name):
            return []
        root = self._parse_xml_part(part_name)
        if root is None:
            return []
        rows: list[AncillaryItem] = []
        comment_by_paragraph_id: dict[str, str] = {}
        for comment in child_elements(root, "w", "comment"):
            comment_id = attr(comment, "w", "id")
            if not comment_id:
                continue
            self.inline.revisions.ranges.clear()
            content = self.content.read(comment, part_name)
            row = self._try_emit_item(
                comment_id,
                f"comments.{comment_id}",
                content,
                rows,
                author=attr(comment, "w", "author") or "",
                date=attr(comment, "w", "date") or "",
            )
            if row is not None:
                anchor = self._comment_anchors.get(comment_id)
                if anchor:
                    row["anchor"] = anchor
                paragraph_id = self._last_paragraph_id(comment)
                if paragraph_id:
                    comment_by_paragraph_id[paragraph_id] = comment_id
        if self.plan.needs(DocxFeature.COMMENT_THREADING):
            self._apply_comment_thread_metadata(rows, comment_by_paragraph_id)
        return rows

    # ── shared helpers ────────────────────────────────────────────

    def _try_emit_item(
        self,
        item_id: str,
        loc: str,
        content: AncillaryContent,
        rows: list[AncillaryItem],
        *,
        author: str = "",
        date: str = "",
    ) -> AncillaryItem | None:
        """Build and append an AncillaryItem if the content is non-empty."""
        if not (content["text"].strip() or has_objects(content["runs"])):
            return None
        row: AncillaryItem = {
            "id": item_id,
            "loc": loc,
            "text": content["text"],
            "runs": content["runs"],
            "searchUnits": content.get("searchUnits", []),
        }
        if author:
            row["author"] = author
        if date:
            row["date"] = date
        if self.plan.needs(DocxFeature.RAW_HINTS) and self.options.include_raw_hints and content["rawHints"]:
            row["rawHints"] = content["rawHints"]
        rows.append(row)
        return row

    @staticmethod
    def _last_paragraph_id(comment: ET.Element) -> str | None:
        """Locate the paragraph identity used by Word's modern comment-thread part."""
        paragraph_id: str | None = None
        for element in comment.iter():
            if local_name(element.tag) == "p":
                candidate = local_attr(element, "paraId")
                if candidate:
                    paragraph_id = candidate
        return paragraph_id

    def _apply_comment_thread_metadata(
        self,
        rows: list[AncillaryItem],
        comment_by_paragraph_id: Mapping[str, str],
    ) -> None:
        """Merge Word 2012+ reply and resolved-state metadata into classic comments."""
        part_name = "word/commentsExtended.xml"
        if not rows or not self.package.exists(part_name):
            return
        root = self._parse_xml_part(part_name)
        if root is None:
            return
        by_id = {item["id"]: item for item in rows if item["id"] is not None}
        for element in root.iter():
            if local_name(element.tag) != "commentEx":
                continue
            paragraph_id = local_attr(element, "paraId")
            comment_id = comment_by_paragraph_id.get(paragraph_id or "")
            if comment_id is None:
                continue
            item = by_id.get(comment_id)
            if item is None:
                continue
            parent_paragraph_id = local_attr(element, "paraIdParent")
            if parent_paragraph_id:
                parent_id = comment_by_paragraph_id.get(parent_paragraph_id)
                if parent_id:
                    item["parentId"] = parent_id
                else:
                    append_warning(
                        self.warnings,
                        "COMMENT_PARENT_UNRESOLVED",
                        "Comment reply points to a parent that is absent from comments.xml.",
                        part=part_name,
                        block_id=comment_id,
                    )
            if _word_bool(local_attr(element, "done")):
                item["resolved"] = True

    def _parse_xml_part(self, part_name: str) -> ET.Element | None:
        """Read an XML part; log a warning and return None on failure."""
        try:
            with self.package.open_entry(part_name) as stream:
                return self.compatibility.read(stream, part_name)
        except Exception as exc:
            append_warning(
                self.warnings,
                "ANCILLARY_XML_PARSE_FAILED",
                f"Failed to parse {part_name}: {exc}",
                part=part_name,
            )
            return None

    def _next_block_id(self, part: str) -> str:
        """Generate a lightweight locator id for ancillary inline warnings."""
        self._block_index += 1
        return f"{part}#{self._block_index}"


def _word_bool(value: str | None) -> bool:
    """Interpret the OOXML on/off lexical values used by comment completion state."""
    return value is not None and value.lower() not in {"0", "false", "off", "none"}
