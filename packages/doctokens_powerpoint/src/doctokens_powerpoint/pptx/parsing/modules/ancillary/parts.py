"""Extract saved speaker notes."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_core.contracts.models import ParseWarning

from ....ooxml.compatibility import read_content_part
from ....ooxml.namespaces import first_child, local_name
from ....ooxml.package import PackageReader
from ....ooxml.unsupported import UNPARSED
from ..slides.runs import tx_body_text

NOTES_SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"


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

    def notes_for(self, slide_part: str, *, source_paragraphs: list[str] | None = None) -> str | None:
        relationship = next(
            (record for record in self._relationships.by_source(slide_part) if record.type == NOTES_SLIDE_REL_TYPE),
            None,
        )
        if relationship is None:
            return None
        target = relationship.resolved_target
        if target is None or not self._pkg.exists(target):
            self._warnings.append(
                ParseWarning(
                    code="NOTES_PART_MISSING",
                    message=f"Notes slide part missing: {target}",
                    locator=slide_part,
                )
            )
            return "[Unparsed speaker notes]"
        try:
            root = self._read_xml(target)
        except ET.ParseError as exc:
            self._warnings.append(ParseWarning(code="NOTES_XML_INVALID", message=f"Invalid notes XML: {exc}", locator=target))
            return "[Unparsed speaker notes]"
        c_sld = first_child(root, "p", "cSld")
        sp_tree = first_child(c_sld, "p", "spTree") if c_sld is not None else None
        if sp_tree is None:
            self._warnings.append(ParseWarning("NOTES_MISSING_SPTREE", "Notes part has no shape tree", target))
            return "[Unparsed speaker notes]"
        texts: list[str] = []
        sources: list[str] = []
        for child in sp_tree:
            if child.tag == UNPARSED:
                texts.append(f"[Unparsed shape: {child.get('source', 'shape')}]")
                sources.append("\ufffc")
                continue
            if local_name(child.tag) != "sp":
                continue
            ph = next((node for node in child.iter() if local_name(node.tag) == "ph"), None)
            # Notes contain placeholders for slide number, date/time, and
            # header/footer. They are document chrome, not speaker content.
            ph_type = ph.get("type", "") if ph is not None else ""
            if ph_type in {"sldNum", "dt", "hdr", "ftr", "slideImage"}:
                continue
            shape_sources: list[str] = []
            text = tx_body_text(
                first_child(child, "p", "txBody"),
                target,
                self._warnings,
                source_paragraphs=shape_sources,
            )
            if text:
                texts.append(text)
                sources.append("\n".join(shape_sources))
        if not texts:
            return None
        if source_paragraphs is not None:
            source_paragraphs.extend("\n\n".join(sources).splitlines())
        return "\n\n".join(texts)

    def _read_xml(self, part: str) -> ET.Element:
        return read_content_part(self._pkg, part, self._warnings)
