"""Extract ancillary content: headers, footers, footnotes, endnotes, and comments."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_SDT_CONTENT,
    _TAG_W_SMART_TAG,
    _TAG_W_STRUCTURED_DOCUMENT_TAG,
    _TAG_W_TABLE,
    attr,
    child_elements,
    first_child,
)
from ..core.models import (
    AncillaryContent,
    AncillaryItem,
    AncillaryResult,
    AssetLookup,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    RawHint,
    Run,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.styles import StyleMap
from .inline import InlineParser


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
    ) -> None:
        self.package = package
        self.options = options
        self.warnings = warnings
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
        )
        self._block_index = 0

    def parse(self) -> AncillaryResult:
        """Return five categories of ancillary content."""
        return {
            "headers": self._parse_header_footer("header"),
            "footers": self._parse_header_footer("footer"),
            "footnotes": self._parse_notes("word/footnotes.xml", "footnote"),
            "endnotes": self._parse_notes("word/endnotes.xml", "endnote"),
            "comments": self._parse_comments(),
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
            content = self._container_content(root, name)
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
            content = self._container_content(note, part_name)
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
        for comment in child_elements(root, "w", "comment"):
            comment_id = attr(comment, "w", "id")
            if not comment_id:
                continue
            content = self._container_content(comment, part_name)
            self._try_emit_item(
                comment_id,
                f"comments.{comment_id}",
                content,
                rows,
                author=attr(comment, "w", "author") or "",
                date=attr(comment, "w", "date") or "",
            )
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
    ) -> None:
        """Build and append an AncillaryItem if the content is non-empty."""
        if not (content["text"].strip() or self._has_objects(content["runs"])):
            return
        row: AncillaryItem = {
            "id": item_id,
            "loc": loc,
            "text": content["text"],
            "runs": content["runs"],
        }
        if author:
            row["author"] = author
        if date:
            row["date"] = date
        if self.options.include_raw_hints and content["rawHints"]:
            row["rawHints"] = content["rawHints"]
        rows.append(row)

    def _parse_xml_part(self, part_name: str) -> ET.Element | None:
        """Read an XML part; log a warning and return None on failure."""
        try:
            with self.package.open_entry(part_name) as stream:
                return ET.parse(stream).getroot()
        except Exception as exc:
            self.warnings.append(
                ParseWarning(
                    code="ANCILLARY_XML_PARSE_FAILED",
                    message=f"Failed to parse {part_name}: {exc}",
                    locator=part_name,
                )
            )
            return None

    def _container_content(self, node: ET.Element, part: str) -> AncillaryContent:
        """Extract paragraphs, tables, and inline objects from a container element.

        Uses pre-computed tag names for direct comparison to avoid qualified_name()
        / local_name() calls in the hot path.
        """
        text_parts: list[str] = []
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        for child in node:
            child_tag = child.tag
            if child_tag == _TAG_W_PARAGRAPH:
                p_runs, p_hints = self.inline.paragraph_runs(
                    child, part, self._next_block_id(part), self._paragraph_style_id(child)
                )
                p_text = "".join(run["text"] for run in p_runs)
                if p_text.strip() or self._has_objects(p_runs):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(p_runs)
                    text_parts.append(p_text)
                    raw_hints.extend(p_hints)
            elif child_tag == _TAG_W_TABLE:
                table_content = self._table_content(child, part)
                if table_content["text"].strip() or self._has_objects(table_content["runs"]):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(table_content["runs"])
                    text_parts.append(table_content["text"])
                    raw_hints.extend(table_content["rawHints"])
            elif child_tag in (
                _TAG_W_STRUCTURED_DOCUMENT_TAG,
                _TAG_W_SDT_CONTENT,
                _TAG_W_SMART_TAG,
            ):
                nested = self._container_content(child, part)
                if nested["text"].strip() or self._has_objects(nested["runs"]):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(nested["runs"])
                    text_parts.append(nested["text"])
                    raw_hints.extend(nested["rawHints"])
        return {"text": "\n".join(text_parts), "runs": runs, "rawHints": raw_hints}

    def _table_content(self, tbl: ET.Element, part: str) -> AncillaryContent:
        """Flatten a table in ancillary content to row text while preserving inline runs."""
        text_rows: list[str] = []
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        for tr in child_elements(tbl, "w", "tr"):
            cell_contents = [self._container_content(tc, part) for tc in child_elements(tr, "w", "tc")]
            visible_cells = [cell for cell in cell_contents if cell["text"].strip() or self._has_objects(cell["runs"])]
            if not visible_cells:
                continue
            if runs:
                runs.append({"text": "\n"})
            row_texts: list[str] = []
            for cell_index, cell in enumerate(visible_cells):
                if cell_index:
                    runs.append({"text": " | "})
                runs.extend(cell["runs"])
                row_texts.append(cell["text"].strip())
                raw_hints.extend(cell["rawHints"])
            text_rows.append(" | ".join(text for text in row_texts if text))
        return {"text": "\n".join(text_rows), "runs": runs, "rawHints": raw_hints}

    def _paragraph_style_id(self, p: ET.Element) -> str | None:
        """Read the paragraph style id from paragraph properties."""
        paragraph_properties = first_child(p, "w", "pPr")
        pstyle = first_child(paragraph_properties, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _next_block_id(self, part: str) -> str:
        """Generate a lightweight locator id for ancillary inline warnings."""
        self._block_index += 1
        return f"{part}#{self._block_index}"

    def _has_objects(self, runs: list[Run]) -> bool:
        """Check whether any run carries non-text objects (images, footnotes, equations)."""
        return any("objects" in run for run in runs)
