"""DOCX parse pipeline orchestrator."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from ._version import __version__
from .core.debug import DebugWriter
from .core.metrics import MetricsRecorder
from .core.models import (
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
from .core.package import PackageReader
from .core.relationships import RelationshipIndex
from .diagnostics import record_content_metrics, write_debug_artifacts, write_metrics_debug
from .extractors.ancillary import AncillaryParser
from .extractors.assets import AssetExtractor
from .extractors.body import DocumentBodyParser
from .extractors.objects import EmbeddedObjectExtractor
from .ooxml.numbering import NumberingMap, NumberingParser, NumberingState
from .ooxml.styles import StyleMap, StylesParser


@dataclass
class _ParseResult:
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
    body_parser: DocumentBodyParser
    ancillary: AncillaryResult
    ocr_results: dict[str, str]
    style_rows: list[dict[str, object]]


class DocxParser:
    """Public DOCX parser entry point."""

    def parse(self, docx_source: str | Path | bytes, options: ParseOptions | None = None) -> ParsedDocument:
        """Parse a single DOCX file, creating fresh per-call context for concurrency safety."""
        opts = options or ParseOptions()
        warnings: list[ParseWarning] = []
        output_dir = opts.output_dir
        debug_dir = output_dir / ".debug"
        debug = DebugWriter(debug_dir, enabled=opts.debug)
        metrics = MetricsRecorder()
        source_name, docx_source_path = _source_info(docx_source, metrics)

        with PackageReader(docx_source_path, opts) as package:
            zip_index, content_types, relationships = self._open_package(package, metrics)
            styles = self._resolve_styles(package, warnings, metrics)
            numbering = self._resolve_numbering(package, warnings, metrics)
            assets, asset_lookup = self._index_resources(package, relationships, content_types, warnings, metrics)
            object_lookup, charts, smartarts = self._index_objects(package, relationships, warnings, metrics)

            # OCR pipeline
            ocr_results = self._run_ocr(package, assets, opts)

            body_parser, blocks = self._parse_body(
                package,
                styles,
                opts,
                warnings,
                relationships,
                asset_lookup,
                object_lookup,
                numbering,
                metrics,
            )
            ancillary = self._parse_ancillary(
                package,
                styles,
                opts,
                warnings,
                relationships,
                asset_lookup,
                object_lookup,
                metrics,
            )

            with metrics.stage("style_debug_rows"):
                style_rows = styles.to_debug_list()

        result = _ParseResult(
            source_path=docx_source_path,
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
            body_parser=body_parser,
            ancillary=ancillary,
            ocr_results=ocr_results,
            style_rows=style_rows,
        )
        return self._build_document(result, warnings, metrics, debug, debug_dir, opts)

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
    ) -> StyleMap:
        with metrics.stage("styles"):
            return StylesParser(package, warnings).parse()

    @staticmethod
    def _resolve_numbering(
        package: PackageReader,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
    ) -> NumberingMap:
        with metrics.stage("numbering"):
            return NumberingParser(package, warnings).parse()

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
    ) -> tuple[ObjectLookup, list[Chart], list[SmartArt]]:
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
        opts: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        numbering: NumberingMap,
        metrics: MetricsRecorder,
    ) -> tuple[DocumentBodyParser, list[Block]]:
        body_parser = DocumentBodyParser(
            package,
            styles,
            opts,
            warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            numbering_state=NumberingState(numbering, warnings),
        )
        with metrics.stage("body"):
            blocks = body_parser.parse()
        return body_parser, blocks

    @staticmethod
    def _parse_ancillary(
        package: PackageReader,
        styles: StyleMap,
        opts: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
        metrics: MetricsRecorder,
    ) -> AncillaryResult:
        with metrics.stage("ancillary"):
            return AncillaryParser(
                package,
                styles,
                opts,
                warnings,
                relationships=relationships,
                asset_lookup=asset_lookup,
                object_lookup=object_lookup,
            ).parse()

    # OCR pipeline

    @staticmethod
    def _run_ocr(package: PackageReader, assets: list[ImageAsset], opts: ParseOptions) -> dict[str, str]:
        """Run OCR on embedded images, deduplicating by content hash."""
        provider = getattr(opts, "ocr", None)
        if provider is None:
            return {}

        # Collect unique images by content hash.
        hashes: dict[str, str] = {}  # assetId -> sha256 hex
        unique_images: dict[str, bytes] = {}  # sha256 -> image bytes
        for asset in assets:
            if asset["type"] != "image" or asset.get("source") != "embedded":
                continue
            zip_path = asset.get("zipPath")
            if not zip_path:
                continue
            image_bytes = package.open_entry(zip_path).read()
            h = hashlib.sha256(image_bytes).hexdigest()
            hashes[asset["id"]] = h
            if h not in unique_images:
                unique_images[h] = image_bytes

        if not unique_images:
            return {}

        # Submit OCR jobs in parallel.
        ocr_raw: dict[str, str] = {}  # sha256 -> OCR text
        max_workers = getattr(opts, "ocr_workers", 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(provider.extract, img): h for h, img in unique_images.items()}
            for future in as_completed(futures):
                h = futures[future]
                try:
                    ocr_raw[h] = future.result()
                except Exception:
                    ocr_raw[h] = ""

        # Map back to asset IDs.
        result: dict[str, str] = {}
        for asset_id, h in hashes.items():
            result[asset_id] = ocr_raw.get(h, "")
        return result

    # Document assembly

    def _build_document(
        self,
        result: _ParseResult,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
        debug: DebugWriter,
        debug_dir: Path,
        opts: ParseOptions,
    ) -> ParsedDocument:
        total_uncompressed = 0
        total_compressed = 0
        for item in result.zip_index:
            total_uncompressed += item["uncompressedSize"]
            total_compressed += item["compressedSize"]
        entry_count = len(result.zip_index)
        package_info: dict[str, object] = {
            "entryCount": entry_count,
            "totalUncompressedBytes": total_uncompressed,
            "totalCompressedBytes": total_compressed,
        }
        metrics.set_counter("entryCount", entry_count)
        metrics.set_counter("zipUncompressedBytes", total_uncompressed)
        metrics.set_counter("zipCompressedBytes", total_compressed)
        metadata: dict[str, object] = {
            "sourceFile": result.source_name,
            "sourcePath": (str(result.source_path) if not isinstance(result.source_path, bytes) else ""),
            "format": "docx",
            "parser": "docx_llm_parser",
            "parserVersion": __version__,
            "sectionRefs": result.body_parser.section_refs,
        }

        parsed = ParsedDocument(
            metadata=metadata,
            package_info=package_info,
            blocks=result.blocks,
            relationships=list(result.relationships.records),
            styles=list(result.styles.records.values()),
            warnings=warnings,
            debug_dir=str(debug_dir) if opts.debug else None,
            content_types=result.content_types,
            assets=result.assets,
            charts=result.charts,
            smartarts=result.smartarts,
            headers=result.ancillary["headers"],
            footers=result.ancillary["footers"],
            footnotes=result.ancillary["footnotes"],
            endnotes=result.ancillary["endnotes"],
            comments=result.ancillary["comments"],
            numbering=result.numbering.to_debug_dict(),
            ocr_results=result.ocr_results,
        )
        record_content_metrics(parsed, metrics)

        with metrics.stage("debug_write"), debug:
            write_debug_artifacts(
                debug,
                result.zip_index,
                result.content_types,
                result.relationships,
                result.style_rows,
                result.body_parser,
                parsed,
            )
            parsed.metrics = metrics.snapshot()
            write_metrics_debug(debug, parsed)
        return parsed


def _source_info(docx_source: str | Path | bytes, metrics: MetricsRecorder) -> tuple[str, str | Path | bytes]:
    if isinstance(docx_source, bytes):
        metrics.set_counter("inputBytes", len(docx_source))
        return "stream", docx_source
    path = Path(docx_source)
    metrics.set_counter("inputBytes", path.stat().st_size)
    return path.name, path
