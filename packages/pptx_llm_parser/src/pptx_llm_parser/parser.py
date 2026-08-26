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
class _ParseContext:
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
class _SlideRef:
    """Validated presentation relationship for one slide entry."""

    relationship_id: str
    slide_id: str
    part: str


def _normalise_slide_navigation(slide: SlideBlock, refs: tuple[_SlideRef, ...], slide_number: int) -> None:
    """Convert internal part paths and next/previous actions into useful slide anchors."""
    target_by_part = {ref.part: f"#slide{index}" for index, ref in enumerate(refs, start=1)}

    def normalise(target: str) -> str:
        if target in target_by_part:
            return target_by_part[target]
        marker = "ppaction://hlinkshowjump?jump="
        if not target.startswith(marker):
            return target
        jump = target.removeprefix(marker).lower()
        target_index = {
            "nextslide": min(slide_number + 1, len(refs)),
            "previousslide": max(slide_number - 1, 1),
            "firstslide": 1,
            "lastslide": len(refs),
        }.get(jump)
        return f"#slide{target_index}" if target_index else target

    for shape in slide["shapes"]:
        link = shape.get("link")
        if link:
            shape["link"] = normalise(link)
        for run in shape.get("runs", []):
            run_link = run.get("link")
            if run_link:
                run["link"] = normalise(run_link)


@dataclass(slots=True)
class _SlideParseResult:
    """Intermediate slide product shared by full and streaming parses."""

    slide: SlideBlock


class _SlideSequence:
    """Validate the presentation slide list once and parse it in document order."""

    def __init__(
        self,
        pkg: PackageReader,
        context: _ParseContext,
        warnings: list[ParseWarning],
        plan: PptxParsePlan,
    ) -> None:
        self._pkg = pkg
        self._context = context
        self._warnings = warnings
        self._refs = tuple(self._collect_refs())
        self._parser = SlideParser(
            warnings,
            context.asset_lookup,
            context.chart_lookup,
            context.smartart_lookup,
            context.layout_lookup,
            context.resolver,
            context.slide_size,
            context.theme,
            context.hyperlinks,
            plan,
        )

    @property
    def refs(self) -> tuple[_SlideRef, ...]:
        return self._refs

    def _collect_refs(self) -> list[_SlideRef]:
        sld_id_lst = first_child(self._context.presentation_root, "p", "sldIdLst")
        if sld_id_lst is None:
            self._warnings.append(
                ParseWarning(
                    code="PRESENTATION_MISSING_SLDIDLST",
                    message="Missing p:sldIdLst",
                    locator=PRESENTATION_PART,
                )
            )
            return []
        refs: list[_SlideRef] = []
        for sld_id_el in sld_id_lst:
            if local_name(sld_id_el.tag) != "sldId":
                continue
            rid = attr(sld_id_el, "r", "id")
            if rid is None:
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_MISSING_RID",
                        message="p:sldId missing r:id",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            relationship = self._context.relationships.get(PRESENTATION_PART, rid)
            if relationship is None or relationship.resolved_target is None:
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_REL_UNRESOLVED",
                        message=f"Unresolved slide relationship {rid}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            part = relationship.resolved_target
            if not self._pkg.exists(part):
                self._warnings.append(
                    ParseWarning(
                        code="SLIDE_PART_MISSING",
                        message=f"Slide part missing: {part}",
                        locator=PRESENTATION_PART,
                    )
                )
                continue
            refs.append(_SlideRef(rid, sld_id_el.get("id", ""), part))
        return refs

    def iter_results(self, *, start_slide: int = 1) -> Generator[_SlideParseResult, None, None]:
        slide_number = 0
        for ref in self._refs:
            try:
                root = self._read_xml(ref.part)
            except ET.ParseError as exc:
                self._warnings.append(
                    ParseWarning(code="SLIDE_XML_INVALID", message=f"Invalid slide XML: {exc}", locator=ref.part)
                )
                continue
            hidden, shapes, background = self._parser.parse_slide(root, ref.part)
            slide_number += 1
            slide = SlideBlock(
                id=f"slide{slide_number}",
                type="slide",
                n=slide_number,
                part=ref.part,
                sldId=ref.slide_id,
                hidden=hidden,
                shapes=shapes,
                notes=self._context.notes.notes_for(ref.part),
                background=background,
                commentRefs=[],
                section=self._context.section_by_slide_id.get(ref.slide_id),
            )
            _normalise_slide_navigation(slide, self._refs, slide_number)
            if slide_number >= start_slide:
                yield _SlideParseResult(slide)

    def _read_xml(self, part: str) -> ET.Element:
        return self._pkg.read_xml(part)


class _CommentAttachmentPlan:
    """Group raw comments by validated slide locator before slide parsing."""

    def __init__(self, comments: list[CommentItem], refs: tuple[_SlideRef, ...]) -> None:
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
        with PackageReader(source, options) as pkg:
            pkg.validate()
            context = self._build_context(pkg, warnings, resolved_plan)
            sequence = _SlideSequence(pkg, context, warnings, resolved_plan)
            slides = [result.slide for result in sequence.iter_results()]
            charts = context.objects.loaded_charts
            smartarts = context.objects.loaded_smartarts
            _CommentAttachmentPlan(context.comments, sequence.refs).attach_all(slides, context.slide_size)
            ocr_results = self._run_ocr(pkg, context.assets, slides, options) if resolved_plan.needs(PptxFeature.OCR) else {}
        parsed = ParsedPresentation(
            slides=slides,
            slide_size=context.slide_size,
            assets=context.assets,
            charts=charts,
            smartarts=smartarts,
            theme=context.theme,
            comments=context.comments,
            sections=context.sections,
            warnings=warnings,
            ocr_results=ocr_results,
        )
        record_metrics(parsed, metrics)
        parsed.metrics = metrics.snapshot()
        parsed.report = ParseReport(
            "pptx",
            1,
            {
                "slideCount": len(parsed.slides),
                "shapeCount": sum(len(slide["shapes"]) for slide in parsed.slides),
                "imageCount": sum(1 for asset in parsed.assets if asset.get("type") == "image"),
                "mediaCount": sum(1 for asset in parsed.assets if asset.get("type") == "media"),
                "chartCount": len(parsed.charts),
                "smartartCount": len(parsed.smartarts),
                "commentCount": len(parsed.comments),
            },
            tuple(parsed.warnings),
            parsed.metrics,
        )
        return parsed

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
        with PackageReader(source, options) as pkg:
            pkg.validate()
            plan = PptxParsePlan.session()
            context = self._build_context(pkg, warnings, plan)
            sequence = _SlideSequence(pkg, context, warnings, plan)
            comment_plan = _CommentAttachmentPlan(context.comments, sequence.refs)
            for result in sequence.iter_results(start_slide=start_slide):
                slide = result.slide
                parsed = ParsedPresentation(
                    slides=[slide],
                    slide_size=context.slide_size,
                    assets=context.assets,
                    charts=context.objects.loaded_charts,
                    smartarts=context.objects.loaded_smartarts,
                    theme=context.theme,
                    comments=context.comments,
                    sections=context.sections,
                    warnings=warnings,
                )
                if options.ocr is not None:
                    parsed.ocr_results = self._run_ocr(pkg, context.assets, [slide], options)
                comment_plan.attach(slide, context.slide_size)
                yield slide, parsed

    def _build_context(
        self,
        pkg: PackageReader,
        warnings: list[ParseWarning],
        plan: PptxParsePlan,
    ) -> _ParseContext:
        relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
        assets, asset_lookup = AssetExtractor(pkg, relationships, warnings).extract()
        objects = EmbeddedObjectExtractor(pkg, relationships, warnings)
        chart_lookup = objects.lazy_charts()
        smartart_lookup, layout_lookup = objects.lazy_smartarts()
        theme_parser = ThemeParser(pkg, relationships, warnings) if plan.needs(PptxFeature.THEME_AND_LAYOUT) else None
        theme = theme_parser.parse() if theme_parser is not None else {}
        hyperlinks = {
            (record.source_part, record.id): record.resolved_target
            for record in relationships.records
            if record.type in {HYPERLINK_RELATIONSHIP_TYPE, _SLIDE_RELATIONSHIP_TYPE}
            if record.resolved_target is not None
        }
        presentation_root = self._read_xml(pkg, PRESENTATION_PART)
        sections, section_by_slide_id = self._parse_sections(presentation_root)
        return _ParseContext(
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
                LayoutMasterResolver(pkg, relationships, warnings, theme, theme_parser=theme_parser)
                if plan.needs(PptxFeature.THEME_AND_LAYOUT)
                else None
            ),
            notes=NotesParser(pkg, relationships, warnings),
            comments=CommentsParser(pkg, relationships, warnings).parse(),
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
        pkg: PackageReader,
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
            for primary_id, result in batch_results.items():
                record = result.to_record()
                for asset_id in aliases[primary_id]:
                    results[asset_id] = cast(OcrStoredResult, dict(record))
            pending.clear()
            aliases.clear()
            pending_bytes = 0

        for zip_path, asset_ids in asset_ids_by_path.items():
            try:
                with pkg.open_entry(zip_path) as stream:
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
    def _read_xml(pkg: PackageReader, part: str) -> ET.Element:
        return pkg.read_xml(part)

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
