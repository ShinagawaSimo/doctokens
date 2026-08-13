"""PPTX parser orchestration."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from .core.constants import attr, first_child, local_name
from .core.models import ParsedPresentation, ParseOptions, SlideBlock
from .core.package import PackageReader
from .extractors.slides import SlideParser

PRESENTATION_PART = "ppt/presentation.xml"


class PptxParser:
    """Parse a PPTX file into a ParsedPresentation."""

    def parse(self, source: str | Path | bytes, options: ParseOptions) -> ParsedPresentation:
        warnings: list[ParseWarning] = []
        with PackageReader(source, options) as pkg:
            pkg.validate()
            relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
            presentation_root = self._read_xml(pkg, PRESENTATION_PART)
            slide_size = self._parse_slide_size(presentation_root, warnings)
            slides = self._parse_slide_refs(pkg, relationships, presentation_root, warnings)
        return ParsedPresentation(slides=slides, slide_size=slide_size, warnings=warnings)

    @staticmethod
    def _read_xml(pkg: PackageReader, part: str) -> ET.Element:
        with pkg.open_entry(part) as stream:
            return ET.parse(stream).getroot()

    def _parse_slide_size(self, presentation_root: ET.Element, warnings: list[ParseWarning]) -> tuple[int, int] | None:
        node = first_child(presentation_root, "p", "sldSz")
        if node is None:
            warnings.append(ParseWarning(code="PRESENTATION_MISSING_SLDSZ", message="Missing p:sldSz", locator=PRESENTATION_PART))
            return None
        try:
            return int(node.get("cx", "")), int(node.get("cy", ""))
        except ValueError:
            warnings.append(ParseWarning(code="SLDSZ_INVALID", message="Invalid p:sldSz dimensions", locator=PRESENTATION_PART))
            return None

    def _parse_slide_refs(
        self,
        pkg: PackageReader,
        relationships: RelationshipIndex,
        presentation_root: ET.Element,
        warnings: list[ParseWarning],
    ) -> list[SlideBlock]:
        sld_id_lst = first_child(presentation_root, "p", "sldIdLst")
        if sld_id_lst is None:
            warnings.append(
                ParseWarning(
                    code="PRESENTATION_MISSING_SLDIDLST",
                    message="Missing p:sldIdLst",
                    locator=PRESENTATION_PART,
                )
            )
            return []

        slides: list[SlideBlock] = []
        for sld_id_el in list(sld_id_lst):
            if local_name(sld_id_el.tag) != "sldId":
                continue
            rid = attr(sld_id_el, "r", "id")
            if rid is None:
                warnings.append(
                    ParseWarning(
                        code="SLIDE_MISSING_RID",
                        message="p:sldId missing r:id",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            relationship = relationships.get(PRESENTATION_PART, rid)
            if relationship is None or relationship.resolved_target is None:
                warnings.append(
                    ParseWarning(
                        code="SLIDE_REL_UNRESOLVED",
                        message=f"Unresolved slide relationship {rid}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            part = relationship.resolved_target
            if not pkg.exists(part):
                warnings.append(
                    ParseWarning(
                        code="SLIDE_PART_MISSING",
                        message=f"Slide part missing: {part}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            root = self._read_xml(pkg, part)
            hidden, texts = SlideParser(warnings).parse_slide(root, part)
            n = len(slides) + 1
            slides.append(
                SlideBlock(
                    id=f"slide{n}",
                    type="slide",
                    n=n,
                    part=part,
                    sldId=sld_id_el.get("id", ""),
                    hidden=hidden,
                    text=texts,
                )
            )
        return slides
