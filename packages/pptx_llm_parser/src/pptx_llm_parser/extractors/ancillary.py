"""Ancillary content: speaker notes and comments."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import first_child, local_name
from ..core.models import CommentItem
from ..core.package import PackageReader
from .slides import tx_body_text

NOTES_SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENT_AUTHORS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"


class NotesParser:
    """Extract per-slide speaker notes."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings

    def notes_for(self, slide_part: str) -> str | None:
        target = self._target_for(slide_part, NOTES_SLIDE_REL_TYPE)
        if target is None:
            return None
        if not self._pkg.exists(target):
            self._warnings.append(
                ParseWarning(
                    code="NOTES_PART_MISSING",
                    message=f"Notes slide part missing: {target}",
                    locator=slide_part,
                )
            )
            return None
        root = self._read_xml(target)
        c_sld = first_child(root, "p", "cSld")
        sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
        if sp_tree is None:
            return None
        texts: list[str] = []
        for child in sp_tree:
            if local_name(child.tag) != "sp":
                continue
            text = tx_body_text(first_child(child, "p", "txBody"), target, self._warnings)
            if text:
                texts.append(text)
        if not texts:
            return None
        return "\n\n".join(texts)

    def _target_for(self, source_part: str, rel_type: str) -> str | None:
        for record in self._relationships.by_source(source_part):
            if record.type == rel_type:
                return record.resolved_target
        return None

    def _read_xml(self, part: str) -> ET.Element:
        with self._pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()


class CommentsParser:
    """Extract modern (p15) threaded comments with author names."""

    def __init__(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self._pkg = pkg
        self._relationships = relationships
        self._warnings = warnings

    def parse(self) -> list[CommentItem]:
        authors = self._read_authors()
        comments: list[CommentItem] = []
        for record in self._relationships.by_type(COMMENTS_REL_TYPE):
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                self._warnings.append(
                    ParseWarning(
                        code="COMMENTS_PART_MISSING",
                        message=f"Comments part missing: {part}",
                        locator=record.source_part,
                    )
                )
                continue
            root = self._read_xml(part)
            for element in root.iter():
                if local_name(element.tag) != "cm":
                    continue
                index = len(comments) + 1
                item: CommentItem = {
                    "id": f"cmt{index}",
                    "text": self._comment_text(element),
                    "author": authors.get(element.get("authorId", ""), ""),
                }
                date = element.get("dt")
                if date:
                    item["date"] = date
                parent_id = element.get("parentId")
                if parent_id:
                    item["parentId"] = parent_id
                comments.append(item)
        return comments

    def _read_authors(self) -> dict[str, str]:
        authors: dict[str, str] = {}
        for record in self._relationships.by_type(COMMENT_AUTHORS_REL_TYPE):
            part = record.resolved_target
            if part is None or not self._pkg.exists(part):
                continue
            root = self._read_xml(part)
            for element in root.iter():
                if local_name(element.tag) != "cmAuthor":
                    continue
                author_id = element.get("id")
                name = element.get("name")
                if author_id and name:
                    authors[author_id] = name
        return authors

    @staticmethod
    def _comment_text(cm: ET.Element) -> str:
        parts = [element.text for element in cm.iter() if local_name(element.tag) == "t" and element.text is not None]
        return "".join(parts)

    def _read_xml(self, part: str) -> ET.Element:
        with self._pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()
