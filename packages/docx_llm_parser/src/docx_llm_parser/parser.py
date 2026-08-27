"""DOCX parse pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ooxml_llm_core.models import ParseReport

from ._version import __version__
from .core.metrics import MetricsRecorder
from .core.models import (
    AncillaryResult,
    AssetLookup,
    Block,
    Chart,
    ContentTypes,
    ImageAsset,
    ObjectLookup,
    OcrStoredResult,
    ParsedDocument,
    ParseOptions,
    ParseWarning,
    SmartArt,
    ZipEntryInfo,
)
from .core.package import PackageReader
from .core.relationships import RelationshipIndex
from .diagnostics import record_content_metrics
from .extractors.ancillary import AncillaryParser
from .extractors.assets import AssetExtractor
from .extractors.body import DocumentBodyParser
from .extractors.objects import EmbeddedObjectExtractor
from .ooxml.numbering import NumberingMap, NumberingParser, NumberingState
from .ooxml.styles import StyleMap, StylesParser
from .plan import DocxFeature, DocxParsePlan

_MAX_OCR_BATCH_BYTES = 64 * 1024 * 1024


@dataclass
class _DocumentParseResult:
    """Intermediate results from each pipeline stage, bundled for document assembly."""

    source_path: str | Path | bytes
    source_name: str
    zip_index: list[ZipEntryInfo]
    content_types: ContentTypes
    relationships: RelationshipIndex
    styles: StyleMap
    numbering: NumberingMap
    assets: list[ImageAsset]
    charts: list[Chart]
    smartarts: list[SmartArt]
    blocks: list[Block]
    ancillary: AncillaryResult
    ocr_results: dict[str, OcrStoredResult]


class DocxParser:
    """Public DOCX parser entry point."""

    def parse(
        self,
        docx_source: str | Path | bytes,
        options: ParseOptions | None = None,
        *,
        plan: DocxParsePlan | None = None,
    ) -> ParsedDocument:
        """Parse a single DOCX file, creating fresh per-call context for concurrency safety."""
        parse_options = options or ParseOptions()
        resolved_plan = plan or DocxParsePlan.session()
        warnings: list[ParseWarning] = []
        metrics = MetricsRecorder()
        source_name, source_path = _describe_source(docx_source, metrics)

        with PackageReader(source_path, parse_options) as package:
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

            with metrics.stage("ocr"):
                ocr_results = self._run_ocr(package, assets, parse_options) if resolved_plan.needs(DocxFeature.OCR) else {}

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
        )
        return self._build_document(parse_result, warnings, metrics)

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
        if not plan.needs(DocxFeature.EMBEDDED_DETAILS):
            return {}, [], []
        with metrics.stage("embedded_objects"):
            return EmbeddedObjectExtractor(
                package=package,
                relationships=relationships,
                warnings=warnings,
            ).extract()

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
            ).parse()

    # OCR pipeline

    @staticmethod
    def _run_ocr(
        package: PackageReader,
        assets: list[ImageAsset],
        parse_options: ParseOptions,
    ) -> dict[str, OcrStoredResult]:
        """Run fail-soft OCR in bounded batches, reusing shared media parts."""
        provider = getattr(parse_options, "ocr", None)
        if provider is None:
            return {}

        asset_ids_by_path: dict[str, list[str]] = {}
        for asset in assets:
            if asset["type"] != "image" or asset.get("source") != "embedded":
                continue
            zip_path = asset.get("zipPath")
            if not zip_path:
                continue
            asset_ids_by_path.setdefault(zip_path, []).append(asset["id"])

        from ocr_llm_core import OcrResult, run_ocr_batch

        results: dict[str, OcrStoredResult] = {}
        pending: dict[str, bytes] = {}
        aliases: dict[str, list[str]] = {}
        pending_bytes = 0
        item_limit = max(1, parse_options.ocr_workers * 2)

        def flush() -> None:
            nonlocal pending_bytes
            batch_results = run_ocr_batch(
                pending,
                provider,
                max_workers=parse_options.ocr_workers,
                timeout=parse_options.ocr_timeout,
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
                with package.open_entry(zip_path) as stream:
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

    # Document assembly

    def _build_document(
        self,
        parse_result: _DocumentParseResult,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
    ) -> ParsedDocument:
        total_uncompressed = 0
        total_compressed = 0
        for zip_entry in parse_result.zip_index:
            total_uncompressed += zip_entry["uncompressedSize"]
            total_compressed += zip_entry["compressedSize"]
        entry_count = len(parse_result.zip_index)
        package_info: dict[str, object] = {
            "entryCount": entry_count,
            "totalUncompressedBytes": total_uncompressed,
            "totalCompressedBytes": total_compressed,
        }
        metrics.set_counter("entryCount", entry_count)
        metrics.set_counter("zipUncompressedBytes", total_uncompressed)
        metrics.set_counter("zipCompressedBytes", total_compressed)
        metadata: dict[str, object] = {
            "sourceFile": parse_result.source_name,
            "sourcePath": (str(parse_result.source_path) if not isinstance(parse_result.source_path, bytes) else ""),
            "format": "docx",
            "parser": "docx_llm_parser",
            "parserVersion": __version__,
        }

        parsed_document = ParsedDocument(
            metadata=metadata,
            package_info=package_info,
            blocks=parse_result.blocks,
            relationships=list(parse_result.relationships.records),
            styles=list(parse_result.styles.records.values()),
            warnings=warnings,
            content_types=parse_result.content_types,
            assets=parse_result.assets,
            charts=parse_result.charts,
            smartarts=parse_result.smartarts,
            headers=parse_result.ancillary["headers"],
            footers=parse_result.ancillary["footers"],
            footnotes=parse_result.ancillary["footnotes"],
            endnotes=parse_result.ancillary["endnotes"],
            comments=parse_result.ancillary["comments"],
            ocr_results=parse_result.ocr_results,
        )
        record_content_metrics(parsed_document, metrics)
        parsed_document.metrics = metrics.snapshot()
        parsed_document.report = ParseReport(
            "docx",
            1,
            {
                "pageCount": max((block.get("page", 1) for block in parsed_document.blocks), default=1),
                "blockCount": len(parsed_document.blocks),
                "tableCount": sum(1 for block in parsed_document.blocks if block["type"] == "table"),
                "imageCount": len(parsed_document.assets),
                "chartCount": len(parsed_document.charts),
                "smartartCount": len(parsed_document.smartarts),
                "commentCount": len(parsed_document.comments),
            },
            tuple(parsed_document.warnings),
            parsed_document.metrics,
        )
        return parsed_document


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


def _describe_source(source: str | Path | bytes, metrics: MetricsRecorder) -> tuple[str, str | Path | bytes]:
    if isinstance(source, bytes):
        metrics.set_counter("inputBytes", len(source))
        return "stream", source
    source_path = Path(source)
    metrics.set_counter("inputBytes", source_path.stat().st_size)
    return source_path.name, source_path
