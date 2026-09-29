"""Slide sequence."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ..core.constants import attr, first_child, local_name
from ..core.models import (
    AssetLookup,
    ChartLookup,
    CommentItem,
    ImageAsset,
    LayoutLookup,
    PresentationSection,
    SlideBlock,
    SmartArtLookup,
)
from ..core.package import PackageReader
from ..ooxml.inheritance import LayoutMasterResolver
from ..plan import PptxParsePlan
from .modules.ancillary.parts import NotesParser
from .modules.resources.objects import EmbeddedObjectExtractor
from .modules.slides.scanner import SlideParser

PRESENTATION_PART = "ppt/presentation.xml"


@dataclass
class _PresentationParseContext:
    """Package-scoped collaborators shared by full and streaming parses."""

    relationships: RelationshipIndex
    assets: list[ImageAsset]
    asset_lookup: AssetLookup
    objects: EmbeddedObjectExtractor
    chart_lookup: ChartLookup
    smartart_lookup: SmartArtLookup
    layout_lookup: LayoutLookup
    theme: dict[str, str]
    hyperlinks: dict[tuple[str, str], str]
    resolver: LayoutMasterResolver | None
    notes: NotesParser | None
    comments: list[CommentItem]
    presentation_root: ET.Element
    slide_size: tuple[int, int] | None
    sections: list[PresentationSection]
    section_by_slide_id: dict[str, str]


@dataclass(frozen=True, slots=True)
class _SlideReference:
    """Validated presentation relationship for one slide entry."""

    relationship_id: str
    slide_id: str
    part: str


def _normalize_slide_navigation(
    slide: SlideBlock,
    slide_references: tuple[_SlideReference, ...],
    slide_number: int,
) -> None:
    """Convert internal part paths and next/previous actions into useful slide anchors."""
    target_by_part = {reference.part: f"#slide{index}" for index, reference in enumerate(slide_references, start=1)}

    def normalize(target: str) -> str:
        if target in target_by_part:
            return target_by_part[target]
        marker = "ppaction://hlinkshowjump?jump="
        if not target.startswith(marker):
            return target
        jump = target.removeprefix(marker).lower()
        target_index = {
            "nextslide": min(slide_number + 1, len(slide_references)),
            "previousslide": max(slide_number - 1, 1),
            "firstslide": 1,
            "lastslide": len(slide_references),
        }.get(jump)
        return f"#slide{target_index}" if target_index else target

    for shape in slide["shapes"]:
        link = shape.get("link")
        if link:
            shape["link"] = normalize(link)
        for run in shape.get("runs", []):
            run_link = run.get("link")
            if run_link:
                run["link"] = normalize(run_link)


def _no_navigation(slide: SlideBlock, references: tuple[_SlideReference, ...], slide_number: int) -> None:
    """No-op strategy for plain output, which does not retain navigation."""


def _no_notes(_slide_part: str) -> str | None:
    """No-op strategy for plans that omit speaker notes."""
    return None


@dataclass(slots=True)
class _ParsedSlide:
    """Intermediate slide product shared by full and streaming parses."""

    slide: SlideBlock


class _SlideSequence:
    """Validate the presentation slide list once and parse it in document order."""

    def __init__(
        self,
        package_reader: PackageReader,
        parse_context: _PresentationParseContext,
        warnings: list[ParseWarning],
        plan: PptxParsePlan,
    ) -> None:
        self._package_reader = package_reader
        self._parse_context = parse_context
        self._warnings = warnings
        self._refs = tuple(self._collect_refs())
        self._parser = SlideParser(
            warnings,
            parse_context.asset_lookup,
            parse_context.chart_lookup,
            parse_context.smartart_lookup,
            parse_context.layout_lookup,
            parse_context.resolver,
            parse_context.slide_size,
            parse_context.theme,
            parse_context.hyperlinks,
            plan,
        )
        self._notes_for = parse_context.notes.notes_for if parse_context.notes is not None else _no_notes
        self._normalize_navigation = _normalize_slide_navigation if self._parser.include_navigation else _no_navigation

    @property
    def refs(self) -> tuple[_SlideReference, ...]:
        return self._refs

    def _collect_refs(self) -> list[_SlideReference]:
        slide_id_list = first_child(self._parse_context.presentation_root, "p", "sldIdLst")
        if slide_id_list is None:
            self._warnings.append(
                ParseWarning(
                    code="PRESENTATION_MISSING_SLDIDLST",
                    message="Missing p:sldIdLst",
                    locator=PRESENTATION_PART,
                )
            )
            return []
        refs: list[_SlideReference] = []
        for slide_id_element in slide_id_list:
            if local_name(slide_id_element.tag) != "sldId":
                continue
            relationship_id = attr(slide_id_element, "r", "id")
            if relationship_id is None:
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_MISSING_RID",
                        message="p:sldId missing r:id",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            relationship = self._parse_context.relationships.get(PRESENTATION_PART, relationship_id)
            if relationship is None or relationship.resolved_target is None:
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_REL_UNRESOLVED",
                        message=f"Unresolved slide relationship {relationship_id}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            part = relationship.resolved_target
            if not self._package_reader.exists(part):
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_PART_MISSING",
                        message=f"Slide part missing: {part}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            refs.append(_SlideReference(relationship_id, slide_id_element.get("id", ""), part))
        return refs

    def iter_results(self, *, start_slide: int = 1) -> Generator[_ParsedSlide, None, None]:
        slide_number = 0
        for ref in self._refs:
            try:
                slide_root = self._read_slide_xml(ref.part)
            except ET.ParseError as exc:
                self._warnings.append(
                    ParseWarning(code="SLIDE_XML_INVALID", message=f"Invalid slide XML: {exc}", locator=ref.part)
                )
                continue
            hidden, shapes, background = self._parser.parse_slide(slide_root, ref.part)
            slide_number += 1
            slide = SlideBlock(
                id=f"slide{slide_number}",
                type="slide",
                n=slide_number,
                part=ref.part,
                sldId=ref.slide_id,
                hidden=hidden,
                shapes=shapes,
                notes=self._notes_for(ref.part),
                background=background,
                commentRefs=[],
                section=self._parse_context.section_by_slide_id.get(ref.slide_id),
            )
            self._normalize_navigation(slide, self._refs, slide_number)
            if slide_number >= start_slide:
                yield _ParsedSlide(slide)

    def _read_slide_xml(self, part: str) -> ET.Element:
        return self._package_reader.read_xml(part)
