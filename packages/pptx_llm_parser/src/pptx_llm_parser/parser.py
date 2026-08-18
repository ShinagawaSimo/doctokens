"""PPTX parser orchestration."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from ooxml_llm_core.debug import DebugWriter
from ooxml_llm_core.metrics import MetricsRecorder
from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

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
    SlideBlock,
    SmartArtLookup,
)
from .core.package import PackageReader
from .diagnostics import record_metrics, write_debug_artifacts
from .extractors.ancillary import CommentsParser, NotesParser
from .extractors.assets import AssetExtractor
from .extractors.objects import EmbeddedObjectExtractor
from .extractors.slides import SlideParser
from .ooxml.inheritance import LayoutMasterResolver
from .ooxml.theme import ThemeParser

PRESENTATION_PART = "ppt/presentation.xml"
HYPERLINK_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
_MAX_OCR_BATCH_BYTES = 64 * 1024 * 1024


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
    resolver: LayoutMasterResolver
    notes: NotesParser
    comments: list[CommentItem]
    presentation_root: ET.Element
    slide_size: tuple[int, int] | None


class PptxParser:
    """Parse a PPTX file into a ParsedPresentation."""

    def parse(self, source: str | Path | bytes, options: ParseOptions) -> ParsedPresentation:
        metrics = MetricsRecorder()
        warnings: list[ParseWarning] = []
        with PackageReader(source, options) as pkg:
            pkg.validate()
            context = self._build_context(pkg, warnings)
            slides = self._parse_slide_refs(
                pkg,
                context.relationships,
                context.presentation_root,
                warnings,
                context.asset_lookup,
                context.chart_lookup,
                context.smartart_lookup,
                context.layout_lookup,
                context.resolver,
                context.slide_size,
                context.notes,
                context.theme,
                context.hyperlinks,
            )
            charts = context.objects.loaded_charts
            smartarts = context.objects.loaded_smartarts
            self._attach_comments(context.comments, slides, context.slide_size)
            ocr_results = self._run_ocr(pkg, context.assets, slides, options)
        parsed = ParsedPresentation(
            slides=slides,
            slide_size=context.slide_size,
            assets=context.assets,
            charts=charts,
            smartarts=smartarts,
            theme=context.theme,
            comments=context.comments,
            warnings=warnings,
            ocr_results=ocr_results,
        )
        record_metrics(parsed, metrics)
        parsed.metrics = metrics.snapshot()
        if options.debug:
            write_debug_artifacts(DebugWriter(options.output_dir / ".debug"), parsed)
        return parsed

    def iter_slides(
        self,
        source: str | Path | bytes,
        options: ParseOptions,
        *,
        start_slide: int = 1,
    ) -> Generator[tuple[SlideBlock, ParsedPresentation], None, None]:
        """Yield slides while the package is open, without materializing the deck.

        Package-level indexes and comments are built once, then each slide XML
        is read and released before the next iteration. The companion parsed
        object contains the shared indexes plus the current slide, so callers
        can render it with the same density functions as ``parse``.
        """
        warnings: list[ParseWarning] = []
        with PackageReader(source, options) as pkg:
            pkg.validate()
            context = self._build_context(pkg, warnings)
            sld_id_lst = first_child(context.presentation_root, "p", "sldIdLst")
            if sld_id_lst is None:
                warnings.append(
                    ParseWarning(
                        code="PRESENTATION_MISSING_SLDIDLST",
                        message="Missing p:sldIdLst",
                        locator=PRESENTATION_PART,
                    )
                )
                return
            slide_parser = SlideParser(
                warnings,
                context.asset_lookup,
                context.chart_lookup,
                context.smartart_lookup,
                context.layout_lookup,
                context.resolver,
                context.slide_size,
                context.theme,
                context.hyperlinks,
            )
            n = 0
            for sld_id_el in (element for element in sld_id_lst if local_name(element.tag) == "sldId"):
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
                relationship = context.relationships.get(PRESENTATION_PART, rid)
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
                n += 1
                try:
                    slide_root = self._read_xml(pkg, part)
                except ET.ParseError as exc:
                    warnings.append(ParseWarning(code="SLIDE_XML_INVALID", message=f"Invalid slide XML: {exc}", locator=part))
                    continue
                hidden, shapes, background = slide_parser.parse_slide(slide_root, part)
                slide = SlideBlock(
                    id=f"slide{n}",
                    type="slide",
                    n=n,
                    part=part,
                    sldId=sld_id_el.get("id", ""),
                    hidden=hidden,
                    shapes=shapes,
                    notes=context.notes.notes_for(part),
                    background=background,
                    commentRefs=[],
                )
                if n < start_slide:
                    continue
                parsed = ParsedPresentation(
                    slides=[slide],
                    slide_size=context.slide_size,
                    assets=context.assets,
                    charts=context.objects.loaded_charts,
                    smartarts=context.objects.loaded_smartarts,
                    theme=context.theme,
                    comments=context.comments,
                    warnings=warnings,
                )
                if options.ocr is not None:
                    parsed.ocr_results = self._run_ocr(pkg, context.assets, [slide], options)
                self._attach_comments(context.comments, [slide], context.slide_size, infer_single=False)
                yield slide, parsed

    def _build_context(self, pkg: PackageReader, warnings: list[ParseWarning]) -> _ParseContext:
        relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
        assets, asset_lookup = AssetExtractor(pkg, relationships, warnings).extract()
        objects = EmbeddedObjectExtractor(pkg, relationships, warnings)
        chart_lookup = objects.lazy_charts()
        smartart_lookup, layout_lookup = objects.lazy_smartarts()
        theme = ThemeParser(pkg, relationships, warnings).parse()
        hyperlinks = {
            (record.source_part, record.id): record.resolved_target
            for record in relationships.by_type(HYPERLINK_REL_TYPE)
            if record.resolved_target is not None
        }
        presentation_root = self._read_xml(pkg, PRESENTATION_PART)
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
            resolver=LayoutMasterResolver(pkg, relationships, warnings, theme),
            notes=NotesParser(pkg, relationships, warnings),
            comments=CommentsParser(pkg, relationships, warnings).parse(),
            presentation_root=presentation_root,
            slide_size=self._parse_slide_size(presentation_root, warnings),
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
        for comment in comments:
            locator = comment.get("slideId")
            candidates = [slide for slide in slides if locator in {slide["id"], slide["part"], slide["sldId"]}]
            if not candidates and infer_single and len(slides) == 1:
                candidates = slides
            if not candidates:
                continue
            slide = candidates[0]
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
        asset_lookup: AssetLookup,
        chart_lookup: ChartLookup,
        smartart_lookup: SmartArtLookup,
        layout_lookup: LayoutLookup,
        resolver: LayoutMasterResolver,
        slide_size: tuple[int, int] | None,
        notes_parser: NotesParser,
        theme: dict[str, str],
        hyperlink_lookup: dict[tuple[str, str], str],
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
        slide_parser = SlideParser(
            warnings,
            asset_lookup,
            chart_lookup,
            smartart_lookup,
            layout_lookup,
            resolver,
            slide_size,
            theme,
            hyperlink_lookup,
        )
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
            try:
                root = self._read_xml(pkg, part)
            except ET.ParseError as exc:
                warnings.append(ParseWarning(code="SLIDE_XML_INVALID", message=f"Invalid slide XML: {exc}", locator=part))
                continue
            hidden, shapes, background = slide_parser.parse_slide(root, part)
            n = len(slides) + 1
            slides.append(
                SlideBlock(
                    id=f"slide{n}",
                    type="slide",
                    n=n,
                    part=part,
                    sldId=sld_id_el.get("id", ""),
                    hidden=hidden,
                    shapes=shapes,
                    notes=notes_parser.notes_for(part),
                    background=background,
                    commentRefs=[],
                )
            )
        return slides
