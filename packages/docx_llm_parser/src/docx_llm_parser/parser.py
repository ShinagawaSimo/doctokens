"""解析流程编排入口。"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ._version import __version__
from .core.debug import DebugWriter
from .core.metrics import MetricsRecorder
from .core.models import (
    Block,
    ContentTypes,
    ParsedDocument,
    ParseOptions,
    ParseWarning,
    ZipEntryInfo,
)
from .core.package import PackageReader
from .core.relationships import RelationshipIndex
from .extractors.ancillary import AncillaryParser
from .extractors.assets import AssetExtractor
from .extractors.body import DocumentBodyParser
from .extractors.objects import EmbeddedObjectExtractor
from .ooxml.numbering import NumberingParser, NumberingState
from .ooxml.styles import StyleMap, StylesParser


class DocxParser:
    """对外暴露的 DOCX 解析器。"""

    def parse(
        self, docx_source: str | Path | bytes, options: ParseOptions | None = None
    ) -> ParsedDocument:
        """解析单个 DOCX；每次调用都创建独立上下文，便于并发。"""
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
            assets, asset_lookup = self._index_resources(
                package, relationships, content_types, warnings, metrics
            )
            object_lookup, charts, smartarts = self._index_objects(
                package, relationships, warnings, metrics
            )

            # OCR pipeline — runs in parallel with body parsing.
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
                package, styles, opts, warnings, relationships, asset_lookup, object_lookup, metrics
            )

            with metrics.stage("style_debug_rows"):
                style_rows = styles.to_debug_list()

        return self._build_document(
            docx_source_path,
            source_name,
            zip_index,
            content_types,
            relationships,
            styles,
            numbering,
            assets,
            charts,
            smartarts,
            blocks,
            body_parser,
            ancillary,
            ocr_results,
            warnings,
            metrics,
            debug,
            debug_dir,
            style_rows,
            opts,
        )

    # ── package helpers ──────────────────────────────────────────

    @staticmethod
    def _open_package(package: PackageReader, metrics: MetricsRecorder) -> tuple[list[ZipEntryInfo], ContentTypes, RelationshipIndex]:
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
    def _resolve_styles(package: PackageReader, warnings: list[ParseWarning], metrics: MetricsRecorder) -> StyleMap:
        with metrics.stage("styles"):
            return StylesParser(package, warnings).parse()

    @staticmethod
    def _resolve_numbering(package: PackageReader, warnings: list[ParseWarning], metrics: MetricsRecorder) -> NumberingParser:
        with metrics.stage("numbering"):
            return NumberingParser(package, warnings).parse()

    @staticmethod
    def _index_resources(
        package: PackageReader,
        relationships: RelationshipIndex,
        content_types: ContentTypes,
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
    ) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
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
    ) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
        asset_lookup: dict[tuple[str, str], dict[str, Any]],
        object_lookup: dict[tuple[str, str], dict[str, Any]],
        numbering: NumberingParser,
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
        asset_lookup: dict[tuple[str, str], dict[str, Any]],
        object_lookup: dict[tuple[str, str], dict[str, Any]],
        metrics: MetricsRecorder,
    ) -> dict[str, list[dict[str, Any]]]:
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

    # ── OCR pipeline ─────────────────────────────────────────────

    @staticmethod
    def _run_ocr(
        package: PackageReader, assets: list[dict[str, Any]], opts: ParseOptions
    ) -> dict[str, str]:
        """Run OCR on embedded images, deduplicating by content hash."""
        provider = getattr(opts, "ocr", None)
        if provider is None:
            return {}

        # Collect unique images by content hash.
        hashes: dict[str, str] = {}  # assetId → sha256 hex
        unique_images: dict[str, bytes] = {}  # sha256 → image bytes
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
        ocr_raw: dict[str, str] = {}  # sha256 → ocr text
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

    # ── build document ───────────────────────────────────────────

    def _build_document(
        self,
        docx_source_path: str | Path | bytes,
        source_name: str,
        zip_index: list[ZipEntryInfo],
        content_types: ContentTypes,
        relationships: RelationshipIndex,
        styles: StyleMap,
        numbering: NumberingParser,
        assets: list[dict[str, Any]],
        charts: list[dict[str, Any]],
        smartarts: list[dict[str, Any]],
        blocks: list[Block],
        body_parser: DocumentBodyParser,
        ancillary: dict[str, list[dict[str, Any]]],
        ocr_results: dict[str, str],
        warnings: list[ParseWarning],
        metrics: MetricsRecorder,
        debug: DebugWriter,
        debug_dir: Path,
        style_rows: list[dict[str, object]],
        opts: ParseOptions,
    ) -> ParsedDocument:
        total_uncompressed = 0
        total_compressed = 0
        for item in zip_index:
            total_uncompressed += item["uncompressedSize"]
            total_compressed += item["compressedSize"]
        entry_count = len(zip_index)
        package_info: dict[str, object] = {
            "entryCount": entry_count,
            "totalUncompressedBytes": total_uncompressed,
            "totalCompressedBytes": total_compressed,
        }
        metrics.set_counter("entryCount", entry_count)
        metrics.set_counter("zipUncompressedBytes", total_uncompressed)
        metrics.set_counter("zipCompressedBytes", total_compressed)
        metadata: dict[str, object] = {
            "sourceFile": source_name,
            "sourcePath": str(docx_source_path) if not isinstance(docx_source_path, bytes) else "",
            "format": "docx",
            "parser": "docx_llm_parser",
            "parserVersion": __version__,
            "sectionRefs": body_parser.section_refs,
        }

        parsed = ParsedDocument(
            metadata=metadata,
            package_info=package_info,
            blocks=blocks,
            relationships=list(relationships.records),
            styles=list(styles.records.values()),
            warnings=warnings,
            debug_dir=str(debug_dir) if opts.debug else None,
            content_types=content_types,
            assets=assets,
            charts=charts,
            smartarts=smartarts,
            headers=ancillary["headers"],
            footers=ancillary["footers"],
            footnotes=ancillary["footnotes"],
            endnotes=ancillary["endnotes"],
            comments=ancillary["comments"],
            numbering=numbering.to_debug_dict(),
            ocr_results=ocr_results,
        )
        self._record_content_metrics(parsed, metrics)

        with metrics.stage("debug_write"), debug:
            self._write_debug_artifacts(
                debug, zip_index, content_types, relationships, style_rows, body_parser, parsed
            )
            parsed.metrics = metrics.snapshot()
            self._write_metrics_debug(debug, parsed)
        return parsed

    # ── debug / metrics helpers (unchanged) ───────────────────────

    def _write_debug_artifacts(
        self,
        debug: DebugWriter,
        zip_index: list[ZipEntryInfo],
        content_types: ContentTypes,
        relationships: RelationshipIndex,
        style_rows: list[dict[str, object]],
        body_parser: DocumentBodyParser,
        parsed: ParsedDocument,
    ) -> None:
        """输出调试中间结果；失败时只追加 warning，不影响主输出。"""
        try:
            debug.write_json(
                "package.json",
                {
                    "zipIndex": zip_index,
                    "contentTypes": content_types,
                    "relationships": relationships.to_debug_list(),
                },
            )
            debug.write_json("styles.json", style_rows)
            debug.write_json("numbering.json", parsed.numbering)
            debug.write_json("blocks.json", parsed.blocks)
            debug.write_json(
                "manifest.json",
                {
                    "assets": parsed.assets,
                    "embedded": {
                        "charts": parsed.charts,
                        "smartarts": parsed.smartarts,
                    },
                    "ancillary": {
                        "headers": parsed.headers,
                        "footers": parsed.footers,
                        "footnotes": parsed.footnotes,
                        "endnotes": parsed.endnotes,
                        "comments": parsed.comments,
                    },
                    "summary": {
                        "blockCount": len(parsed.blocks),
                        "assetCount": len(parsed.assets),
                        "chartCount": len(parsed.charts),
                        "smartartCount": len(parsed.smartarts),
                        "headerCount": len(parsed.headers),
                        "footerCount": len(parsed.footers),
                        "footnoteCount": len(parsed.footnotes),
                        "endnoteCount": len(parsed.endnotes),
                        "commentCount": len(parsed.comments),
                        "styleCount": len(parsed.styles),
                        "relationshipCount": len(parsed.relationships),
                        "warningCount": len(parsed.warnings),
                        "packageInfo": parsed.package_info,
                    },
                },
            )
            debug.write_jsonl("events.jsonl", body_parser.body_events)
            debug.write_json("warnings.json", [asdict(item) for item in parsed.warnings])
        except Exception as exc:
            parsed.warnings.append(
                ParseWarning(
                    code="DEBUG_WRITE_FAILED",
                    message=f"Failed to write debug artifacts: {exc}",
                )
            )

    def _record_content_metrics(self, parsed: ParsedDocument, metrics: MetricsRecorder) -> None:
        """统计输出预算和性能判断需要的节点数量。"""
        stats = self._compute_block_stats(parsed.blocks)
        metrics.set_counter("blockCount", len(parsed.blocks))
        metrics.set_counter("paragraphCount", stats["paragraphCount"])
        metrics.set_counter("headingCount", stats["headingCount"])
        metrics.set_counter("tableCount", stats["tableCount"])
        metrics.set_counter("tableCellCount", stats["tableCellCount"])
        metrics.set_counter("runCount", stats["runCount"])
        metrics.set_counter("maxTableRows", stats["maxTableRows"])
        metrics.set_counter("maxTableCols", stats["maxTableCols"])
        metrics.set_counter("relationshipCount", len(parsed.relationships))
        metrics.set_counter("styleCount", len(parsed.styles))
        metrics.set_counter("assetCount", len(parsed.assets))
        metrics.set_counter("chartCount", len(parsed.charts))
        metrics.set_counter("smartartCount", len(parsed.smartarts))
        metrics.set_counter("headerCount", len(parsed.headers))
        metrics.set_counter("footerCount", len(parsed.footers))
        metrics.set_counter("footnoteCount", len(parsed.footnotes))
        metrics.set_counter("endnoteCount", len(parsed.endnotes))
        metrics.set_counter("commentCount", len(parsed.comments))
        metrics.set_counter("warningCount", len(parsed.warnings))

    def _compute_block_stats(self, blocks: list[Block]) -> dict[str, int]:
        """递归统计正文和单元格内 block 数量。"""
        stats = {
            "paragraphCount": 0,
            "headingCount": 0,
            "tableCount": 0,
            "tableCellCount": 0,
            "runCount": 0,
            "maxTableRows": 0,
            "maxTableCols": 0,
        }
        for block in blocks:
            if block["type"] == "paragraph":
                stats["paragraphCount"] += 1
                if "runs" in block:
                    stats["runCount"] += len(block["runs"])
            elif block["type"] == "heading":
                stats["headingCount"] += 1
                if "runs" in block:
                    stats["runCount"] += len(block["runs"])
            elif block["type"] == "table":
                stats["tableCount"] += 1
                stats["maxTableRows"] = max(stats["maxTableRows"], len(block["rows"]))
                stats["maxTableCols"] = max(stats["maxTableCols"], block["columnCount"])
                for row in block["rows"]:
                    stats["tableCellCount"] += len(row["cells"])
                    for cell in row["cells"]:
                        child_stats = self._compute_block_stats(cell["blocks"])
                        for key, value in child_stats.items():
                            if key.startswith("max"):
                                stats[key] = max(stats[key], value)
                            else:
                                stats[key] += value
        return stats

    def _write_metrics_debug(self, debug: DebugWriter, parsed: ParsedDocument) -> None:
        """单独写 metrics，确保 debug_write 阶段耗时也能落盘。"""
        try:
            debug.write_json("metrics.json", parsed.metrics)
        except Exception as exc:
            parsed.warnings.append(
                ParseWarning(
                    code="METRICS_WRITE_FAILED",
                    message=f"Failed to write metrics debug artifact: {exc}",
                )
            )


def _source_info(
    docx_source: str | Path | bytes, metrics: MetricsRecorder
) -> tuple[str, str | Path | bytes]:
    if isinstance(docx_source, bytes):
        metrics.set_counter("inputBytes", len(docx_source))
        return "stream", docx_source
    path = Path(docx_source)
    metrics.set_counter("inputBytes", path.stat().st_size)
    return path.name, path
