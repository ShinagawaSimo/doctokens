"""PPTX parser orchestration."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.metrics import MetricsRecorder
from ooxml_llm_core.models import ParseReport, ParseWarning
from ooxml_llm_core.relationships import HYPERLINK_RELATIONSHIP_TYPE, RelationshipIndex, office_relationship_type

from .core.constants import attr, first_child, local_name
from .core.models import (
    AssetLookup,
    ChartLookup,
    CommentItem,
    CommentRef,
    ImageAsset,
    LayoutLookup,
    OcrStoredResult,
    ParsedPresentation,
    ParseOptions,
    PresentationSection,
    SlideBlock,
    SmartArtLookup,
)
from .core.package import PackageReader
from .diagnostics import record_metrics
from .extractors.ancillary import CommentsParser, NotesParser
from .extractors.assets import AssetExtractor
from .extractors.objects import EmbeddedObjectExtractor
from .extractors.slides import SlideParser
from .ooxml.inheritance import LayoutMasterResolver
from .ooxml.theme import ThemeParser
from .plan import PptxFeature, PptxParsePlan

PRESENTATION_PART = "ppt/presentation.xml"
_MAX_OCR_BATCH_BYTES = 64 * 1024 * 1024
_SLIDE_RELATIONSHIP_TYPE = office_relationship_type("slide")


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
    notes: NotesParser
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
                notes=self._parse_context.notes.notes_for(ref.part),
                background=background,
                commentRefs=[],
                section=self._parse_context.section_by_slide_id.get(ref.slide_id),
            )
            _normalize_slide_navigation(slide, self._refs, slide_number)
            if slide_number >= start_slide:
                yield _ParsedSlide(slide)

    def _read_slide_xml(self, part: str) -> ET.Element:
        return self._package_reader.read_xml(part)


class _CommentAttachmentPlan:
    """Group raw comments by validated slide locator before slide parsing."""

    def __init__(self, comments: list[CommentItem], refs: tuple[_SlideReference, ...]) -> None:
        self.by_slide_part: dict[str, list[CommentItem]] = {}
        self.unresolved: list[CommentItem] = []
        by_locator: dict[str, str] = {}
        for index, ref in enumerate(refs, start=1):
            by_locator[ref.part] = ref.part
            by_locator[ref.relationship_id] = ref.part
            if ref.slide_id:
                by_locator[ref.slide_id] = ref.part
            by_locator[f"slide{index}"] = ref.part
        for comment in comments:
            locator = comment.get("slideId")
            part = by_locator.get(locator) if isinstance(locator, str) else None
            if part is None:
                self.unresolved.append(comment)
            else:
                self.by_slide_part.setdefault(part, []).append(comment)

    def attach(self, slide: SlideBlock, slide_size: tuple[int, int] | None) -> None:
        comments = self.by_slide_part.pop(slide["part"], [])
        if comments:
            PptxParser._attach_comments(comments, [slide], slide_size, infer_single=False)

    def attach_all(self, slides: list[SlideBlock], slide_size: tuple[int, int] | None) -> None:
        for slide in slides:
            self.attach(slide, slide_size)
        if self.unresolved and len(slides) == 1:
            PptxParser._attach_comments(self.unresolved, slides, slide_size, infer_single=True)


class PptxParser:
    """Parse a PPTX file into a ParsedPresentation."""

    def parse(
        self,
        source: str | Path | bytes,
        options: ParseOptions,
        *,
        plan: PptxParsePlan | None = None,
    ) -> ParsedPresentation:
        resolved_plan = plan or PptxParsePlan.session()
        metrics = MetricsRecorder()
        warnings: list[ParseWarning] = []
        with PackageReader(source, options) as package_reader:
            package_reader.validate()
            parse_context = self._build_parse_context(package_reader, warnings, resolved_plan)
            slide_sequence = _SlideSequence(package_reader, parse_context, warnings, resolved_plan)
            slides = [slide_result.slide for slide_result in slide_sequence.iter_results()]
            charts = parse_context.objects.loaded_charts
            smartarts = parse_context.objects.loaded_smartarts
            _CommentAttachmentPlan(parse_context.comments, slide_sequence.refs).attach_all(
                slides,
                parse_context.slide_size,
            )
            ocr_results = (
                self._run_ocr(package_reader, parse_context.assets, slides, options)
                if resolved_plan.needs(PptxFeature.OCR)
                else {}
            )
        parsed_presentation = ParsedPresentation(
            slides=slides,
            slide_size=parse_context.slide_size,
            assets=parse_context.assets,
            charts=charts,
            smartarts=smartarts,
            theme=parse_context.theme,
            comments=parse_context.comments,
            sections=parse_context.sections,
            warnings=warnings,
            ocr_results=ocr_results,
        )
        record_metrics(parsed_presentation, metrics)
        parsed_presentation.metrics = metrics.snapshot()
        parsed_presentation.report = ParseReport(
            "pptx",
            1,
            {
                "slideCount": len(parsed_presentation.slides),
                "shapeCount": sum(len(slide["shapes"]) for slide in parsed_presentation.slides),
                "imageCount": sum(1 for asset in parsed_presentation.assets if asset.get("type") == "image"),
                "mediaCount": sum(1 for asset in parsed_presentation.assets if asset.get("type") == "media"),
                "chartCount": len(parsed_presentation.charts),
                "smartartCount": len(parsed_presentation.smartarts),
                "commentCount": len(parsed_presentation.comments),
            },
            tuple(parsed_presentation.warnings),
            parsed_presentation.metrics,
        )
        return parsed_presentation

    def iter_slides(
        self,
        source: str | Path | bytes,
        options: ParseOptions,
        *,
        start_slide: int = 1,
    ) -> Generator[tuple[SlideBlock, ParsedPresentation], None, None]:
        """Enumerate slides through a lightweight internal reader.

        Public ``stream``/``iter_slides`` APIs use parse-then-render semantics.
        This internal path remains only for resource lookup code that can stop
        after locating one table without exposing streaming parsing as a public
        contract.
        """
        warnings: list[ParseWarning] = []
        with PackageReader(source, options) as package_reader:
            package_reader.validate()
            plan = PptxParsePlan.session()
            parse_context = self._build_parse_context(package_reader, warnings, plan)
            slide_sequence = _SlideSequence(package_reader, parse_context, warnings, plan)
            comment_plan = _CommentAttachmentPlan(parse_context.comments, slide_sequence.refs)
            for parsed_slide in slide_sequence.iter_results(start_slide=start_slide):
                slide = parsed_slide.slide
                parsed_presentation = ParsedPresentation(
                    slides=[slide],
                    slide_size=parse_context.slide_size,
                    assets=parse_context.assets,
                    charts=parse_context.objects.loaded_charts,
                    smartarts=parse_context.objects.loaded_smartarts,
                    theme=parse_context.theme,
                    comments=parse_context.comments,
                    sections=parse_context.sections,
                    warnings=warnings,
                )
                if options.ocr is not None:
                    parsed_presentation.ocr_results = self._run_ocr(
                        package_reader,
                        parse_context.assets,
                        [slide],
                        options,
                    )
                comment_plan.attach(slide, parse_context.slide_size)
                yield slide, parsed_presentation

    def _build_parse_context(
        self,
        package_reader: PackageReader,
        warnings: list[ParseWarning],
        plan: PptxParsePlan,
    ) -> _PresentationParseContext:
        relationships = RelationshipIndex.from_records(package_reader.read_all_relationships())
        assets, asset_lookup = AssetExtractor(package_reader, relationships, warnings).extract()
        objects = EmbeddedObjectExtractor(package_reader, relationships, warnings)
        chart_lookup = objects.lazy_charts()
        smartart_lookup, layout_lookup = objects.lazy_smartarts()
        theme_parser = ThemeParser(package_reader, relationships, warnings) if plan.needs(PptxFeature.THEME_AND_LAYOUT) else None
        theme = theme_parser.parse() if theme_parser is not None else {}
        hyperlinks = {
            (record.source_part, record.id): record.resolved_target
            for record in relationships.records
            if record.type in {HYPERLINK_RELATIONSHIP_TYPE, _SLIDE_RELATIONSHIP_TYPE}
            if record.resolved_target is not None
        }
        presentation_root = self._read_xml_part(package_reader, PRESENTATION_PART)
        sections, section_by_slide_id = self._parse_sections(presentation_root)
        return _PresentationParseContext(
            relationships=relationships,
            assets=assets,
            asset_lookup=asset_lookup,
            objects=objects,
            chart_lookup=chart_lookup,
            smartart_lookup=smartart_lookup,
            layout_lookup=layout_lookup,
            theme=theme,
            hyperlinks=hyperlinks,
            resolver=(
                LayoutMasterResolver(package_reader, relationships, warnings, theme, theme_parser=theme_parser)
                if plan.needs(PptxFeature.THEME_AND_LAYOUT)
                else None
            ),
            notes=NotesParser(package_reader, relationships, warnings),
            comments=CommentsParser(package_reader, relationships, warnings).parse(),
            presentation_root=presentation_root,
            slide_size=self._parse_slide_size(presentation_root, warnings),
            sections=sections,
            section_by_slide_id=section_by_slide_id,
        )

    @staticmethod
    def _attach_comments(
        comments: list[CommentItem],
        slides: list[SlideBlock],
        slide_size: tuple[int, int] | None,
        *,
        infer_single: bool = True,
    ) -> None:
        """Resolve comment slide/shape references without discarding raw IDs."""
        slide_by_locator = {
            locator: slide for slide in slides for locator in (slide["id"], slide["part"], slide["sldId"]) if locator
        }
        for comment in comments:
            locator = comment.get("slideId")
            slide = slide_by_locator.get(locator) if isinstance(locator, str) else None
            if slide is None and infer_single and len(slides) == 1:
                slide = slides[0]
            if slide is None:
                continue
            comment["slideId"] = slide["id"]
            reference: CommentRef = {"id": comment["id"]}
            x = comment.get("x")
            y = comment.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                if reference not in slide["commentRefs"]:
                    slide["commentRefs"].append(reference)
                continue
            if slide_size is not None and (abs(x) > 1000 or abs(y) > 1000):
                x = round(x / slide_size[0] * 1000)
                y = round(y / slide_size[1] * 1000)
            positioned = [shape for shape in slide["shapes"] if shape.get("x") is not None and shape.get("y") is not None]
            if positioned:
                nearest = min(
                    positioned,
                    key=lambda shape: abs(shape["x"] + shape.get("w", 0) // 2 - x) + abs(shape["y"] + shape.get("h", 0) // 2 - y),
                )
                comment["shapeId"] = nearest["id"]
                reference["shapeId"] = nearest["id"]
            if reference not in slide["commentRefs"]:
                slide["commentRefs"].append(reference)

    @staticmethod
    def _run_ocr(
        package_reader: PackageReader,
        assets: list[ImageAsset],
        slides: list[SlideBlock],
        options: ParseOptions,
    ) -> dict[str, OcrStoredResult]:
        """OCR embedded image assets while preserving normalized outcomes."""
        if options.ocr is None:
            return {}
        referenced_ids = {
            asset_id
            for slide in slides
            for shape in slide["shapes"]
            if shape["type"] == "picture"
            for asset_id in [shape.get("assetId")]
            if isinstance(asset_id, str)
        }
        referenced_ids.update(
            asset_id
            for slide in slides
            for background in [slide.get("background")]
            if background is not None
            for asset_id in [background.get("assetId")]
            if isinstance(asset_id, str)
        )
        asset_ids_by_path: dict[str, list[str]] = {}
        for asset in assets:
            if asset.get("id") not in referenced_ids or asset.get("type") != "image" or asset.get("source") != "embedded":
                continue
            asset_id = asset.get("id")
            zip_path = asset.get("zipPath")
            if not isinstance(asset_id, str) or not isinstance(zip_path, str):
                continue
            asset_ids_by_path.setdefault(zip_path, []).append(asset_id)

        from ocr_llm_core import OcrResult, run_ocr_batch

        results: dict[str, OcrStoredResult] = {}
        pending: dict[str, bytes] = {}
        aliases: dict[str, list[str]] = {}
        pending_bytes = 0
        item_limit = max(1, options.ocr_workers * 2)

        def flush() -> None:
            nonlocal pending_bytes
            batch_results = run_ocr_batch(
                pending,
                options.ocr,
                max_workers=options.ocr_workers,
                timeout=options.ocr_timeout,
            )
            for primary_id, ocr_result in batch_results.items():
                record = ocr_result.to_record()
                for asset_id in aliases[primary_id]:
                    results[asset_id] = cast(OcrStoredResult, dict(record))
            pending.clear()
            aliases.clear()
            pending_bytes = 0

        for zip_path, asset_ids in asset_ids_by_path.items():
            try:
                with package_reader.open_entry(zip_path) as stream:
                    image_bytes = stream.read()
            except Exception as exc:
                record = OcrResult.error("image_read_error", str(exc)).to_record()
                for asset_id in asset_ids:
                    results[asset_id] = cast(OcrStoredResult, dict(record))
                continue
            if pending and (len(pending) >= item_limit or pending_bytes + len(image_bytes) > _MAX_OCR_BATCH_BYTES):
                flush()
            primary_id = asset_ids[0]
            pending[primary_id] = image_bytes
            aliases[primary_id] = asset_ids
            pending_bytes += len(image_bytes)
        if pending:
            flush()
        return results

    @staticmethod
    def _read_xml_part(package_reader: PackageReader, part: str) -> ET.Element:
        return package_reader.read_xml(part)

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

    @staticmethod
    def _parse_sections(presentation_root: ET.Element) -> tuple[list[PresentationSection], dict[str, str]]:
        """Extract PowerPoint's named sections without leaking their GUID storage IDs."""
        sections: list[PresentationSection] = []
        section_by_slide_id: dict[str, str] = {}
        for element in presentation_root.iter():
            if local_name(element.tag) != "section":
                continue
            name = element.get("name", "")
            if not name:
                continue
            slide_ids = [child.get("id", "") for child in element.iter() if local_name(child.tag) == "sldId" and child.get("id")]
            if not slide_ids:
                continue
            sections.append({"name": name, "slideIds": slide_ids})
            for slide_id in slide_ids:
                section_by_slide_id.setdefault(slide_id, name)
        return sections, section_by_slide_id
