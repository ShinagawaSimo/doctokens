"""DOCX parse pipeline orchestrator."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..core.metrics import MetricsRecorder
from ..core.models import (
    AncillaryResult,
    AssetLookup,
    Block,
    Chart,
    ContentTypes,
    ImageAsset,
    ObjectLookup,
    ParsedDocument,
    ParseOptions,
    ParseWarning,
    SmartArt,
    ZipEntryInfo,
)
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.compatibility import DocxCompatibility
from ..ooxml.numbering import NumberingMap, NumberingParser, NumberingState
from ..ooxml.styles import StyleMap, StylesParser
from ..plan import DocxFeature, DocxParsePlan
from .assembly import _build_document, _DocumentParseResult
from .modules.ancillary.parts import AncillaryParser
from .modules.body.scanner import DocumentBodyParser
from .modules.body.textboxes import TextboxReader
from .modules.resources.assets import AssetExtractor
from .modules.resources.objects import EmbeddedObjectExtractor
from .ocr import run_ocr


class DocxParser:
    """Public DOCX parser entry point."""

    def parse(
        self,
        docx_source: str | Path | bytes | PackageReader,
        options: ParseOptions | None = None,
        *,
        plan: DocxParsePlan | None = None,
    ) -> ParsedDocument:
        """Parse a single DOCX file, creating fresh per-call context for concurrency safety."""
        parse_options = options or ParseOptions()
        resolved_plan = plan or DocxParsePlan.session()
        warnings: list[ParseWarning] = []
        metrics = MetricsRecorder()
        metrics.set_counter("moduleCount", len(resolved_plan.module_keys))
        metrics.set_counter("modules", ",".join(resolved_plan.module_keys))
        source_name, source_path = _describe_source(docx_source, metrics)

        with _open_package(docx_source, parse_options) as package:
            zip_index, content_types, relationships = self._open_package(package, metrics)
            needs_inline_content = resolved_plan.needs(DocxFeature.BODY) or _needs_ancillary_content(resolved_plan)
            styles = (
                self._resolve_styles(package, warnings, metrics, resolved_plan)
                if needs_inline_content
                else StyleMap({}, warnings)
            )
            numbering = (
                self._resolve_numbering(package, warnings, metrics, styles)
                if resolved_plan.needs(DocxFeature.BODY)
                else NumberingMap({}, {}, warnings)
            )
            assets, asset_lookup = (
                self._index_resources(package, relationships, content_types, warnings, metrics)
                if resolved_plan.needs(DocxFeature.ASSET_INDEX)
                else ([], {})
            )
            object_lookup, charts, smartarts = self._index_objects(package, relationships, warnings, metrics, resolved_plan)
            compatibility = DocxCompatibility(warnings, asset_lookup)

            with metrics.stage("ocr"):
                ocr_results = run_ocr(package, assets, parse_options) if resolved_plan.needs(DocxFeature.OCR) else {}

            if resolved_plan.needs(DocxFeature.BODY):
                body_parser, blocks = self._parse_body(
                    package,
                    styles,
                    parse_options,
                    warnings,
                    relationships,
                    asset_lookup,
                    object_lookup,
                    numbering,
                    metrics,
                    resolved_plan,
                    compatibility,
                )
                comment_anchors = body_parser.comment_anchors
            else:
                blocks = []
                comment_anchors = {}
            ancillary = self._parse_ancillary(
                package,
                styles,
                parse_options,
                warnings,
                relationships,
                asset_lookup,
                object_lookup,
                comment_anchors,
                metrics,
                resolved_plan,
                compatibility,
                body_parser.inline.textbox_reader if resolved_plan.needs(DocxFeature.BODY) else None,
            )

        parse_result = _DocumentParseResult(
            source_path=source_path,
            source_name=source_name,
            zip_index=zip_index,
            content_types=content_types,
            relationships=relationships,
            styles=styles,
            numbering=numbering,
            assets=assets,
            charts=charts,
            smartarts=smartarts,
            blocks=blocks,
            ancillary=ancillary,
            ocr_results=ocr_results,
            revision_view=str(parse_options.revision_mode),
            alternate_content=compatibility.records,
        )
        return _build_document(parse_result, warnings, metrics)

    # Package helpers

    @staticmethod
    def _open_package(
        package: PackageReader,
        metrics: MetricsRecorder,
    ) -> tuple[list[ZipEntryInfo], ContentTypes, RelationshipIndex]:
        with metrics.stage("zip_index"):
            zip_index = package.read_entry_index()
        with metrics.stage("package_validate"):
            package.validate()
        with metrics.stage("content_types"):
            content_types = package.read_content_types()
        with metrics.stage("relationships"):
            relationships = RelationshipIndex.from_records(package.read_all_relationships())
        return zip_index, content_types, relationships

    @staticmethod
    def _resolve_styles(
        package: PackageReader,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
        plan: DocxParsePlan,
    ) -> StyleMap:
        with metrics.stage("styles"):
            return StylesParser(
                package,
                warnings,
                include_character_formatting=plan.needs(DocxFeature.CHARACTER_FORMATTING),
            ).parse()

    @staticmethod
    def _resolve_numbering(
        package: PackageReader,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
        styles: StyleMap,
    ) -> NumberingMap:
        with metrics.stage("numbering"):
            return NumberingParser(package, warnings, styles.numbering_style_num_ids()).parse()

    @staticmethod
    def _index_resources(
        package: PackageReader,
        relationships: RelationshipIndex,
        content_types: ContentTypes,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
    ) -> tuple[list[ImageAsset], AssetLookup]:
        with metrics.stage("assets"):
            return AssetExtractor(
                package=package,
                relationships=relationships,
                content_types=content_types,
                warnings=warnings,
            ).extract()

    @staticmethod
    def _index_objects(
        package: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
        plan: DocxParsePlan,
    ) -> tuple[ObjectLookup, list[Chart], list[SmartArt]]:
        if not plan.needs(DocxFeature.EMBEDDED_DETAILS) and not plan.needs(DocxFeature.EMBEDDED_SUMMARY):
            return {}, [], []
        with metrics.stage("embedded_objects"):
            return EmbeddedObjectExtractor(
                package=package,
                relationships=relationships,
                warnings=warnings,
            ).extract(summary_only=not plan.needs(DocxFeature.EMBEDDED_DETAILS))

    @staticmethod
    def _parse_body(
        package: PackageReader,
        styles: StyleMap,
        parse_options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        numbering: NumberingMap,
        metrics: MetricsRecorder,
        plan: DocxParsePlan,
        compatibility: DocxCompatibility,
    ) -> tuple[DocumentBodyParser, list[Block]]:
        body_parser = DocumentBodyParser(
            package,
            styles,
            parse_options,
            warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            numbering_state=NumberingState(numbering, warnings),
            plan=plan,
            compatibility=compatibility,
        )
        with metrics.stage("body"):
            blocks = body_parser.parse()
        return body_parser, blocks

    @staticmethod
    def _parse_ancillary(
        package: PackageReader,
        styles: StyleMap,
        parse_options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        comment_anchors: dict[str, str],
        metrics: MetricsRecorder,
        plan: DocxParsePlan,
        compatibility: DocxCompatibility,
        textbox_reader: TextboxReader | None = None,
    ) -> AncillaryResult:
        if not _needs_ancillary_content(plan):
            return {"headers": [], "footers": [], "footnotes": [], "endnotes": [], "comments": []}
        with metrics.stage("ancillary"):
            return AncillaryParser(
                package,
                styles,
                parse_options,
                warnings,
                relationships=relationships,
                asset_lookup=asset_lookup,
                object_lookup=object_lookup,
                comment_anchors=comment_anchors,
                plan=plan,
                compatibility=compatibility,
                textbox_reader=textbox_reader,
            ).parse()


def _needs_ancillary_content(plan: DocxParsePlan) -> bool:
    return any(
        plan.needs(feature)
        for feature in (
            DocxFeature.HEADERS,
            DocxFeature.FOOTERS,
            DocxFeature.FOOTNOTES,
            DocxFeature.ENDNOTES,
            DocxFeature.COMMENTS,
        )
    )


def _describe_source(source: str | Path | bytes | PackageReader, metrics: MetricsRecorder) -> tuple[str, str | Path | bytes]:
    if isinstance(source, PackageReader):
        return "session", source._source
    if isinstance(source, bytes):
        metrics.set_counter("inputBytes", len(source))
        return "stream", source
    source_path = Path(source)
    metrics.set_counter("inputBytes", source_path.stat().st_size)
    return source_path.name, source_path


@contextmanager
def _open_package(source: str | Path | bytes | PackageReader, options: ParseOptions) -> Iterator[PackageReader]:
    if isinstance(source, PackageReader):
        yield source
        return
    with PackageReader(source, options) as package:
        yield package
