"""解析流程编排入口。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

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
from .ooxml.styles import StylesParser


class DocxParser:
    """对外暴露的 DOCX 解析器。"""

    def parse(self, docx_source: str | Path | bytes, options: ParseOptions | None = None) -> ParsedDocument:
        """解析单个 DOCX；每次调用都创建独立上下文，便于并发。"""
        opts = options or ParseOptions()
        warnings: list[ParseWarning] = []
        output_dir = opts.output_dir
        debug_dir = output_dir / ".debug"
        debug = DebugWriter(debug_dir, enabled=opts.debug)
        metrics = MetricsRecorder()
        if isinstance(docx_source, bytes):
            metrics.set_counter("inputBytes", len(docx_source))
            source_name = "stream"
        else:
            path = Path(docx_source)
            metrics.set_counter("inputBytes", path.stat().st_size)
            source_name = path.name

        with PackageReader(docx_source, opts) as package:
            # 先校验包结构和安全阈值，再进入 XML 内容解析。
            with metrics.stage("zip_index"):
                zip_index = package.read_entry_index()
            with metrics.stage("package_validate"):
                package.validate()
            with metrics.stage("content_types"):
                content_types = package.read_content_types()
            with metrics.stage("relationships"):
                relationships = RelationshipIndex.from_records(package.read_all_relationships())

            # styles 先解析，正文阶段才能按真实样式识别 heading。
            with metrics.stage("styles"):
                styles = StylesParser(package, warnings).parse()
            with metrics.stage("numbering"):
                numbering = NumberingParser(package, warnings).parse()
            with metrics.stage("assets"):
                assets, asset_lookup = AssetExtractor(
                    package=package,
                    relationships=relationships,
                    content_types=content_types,
                    warnings=warnings,
                ).extract()
            with metrics.stage("embedded_objects"):
                object_lookup, charts, smartarts = EmbeddedObjectExtractor(
                    package=package,
                    relationships=relationships,
                    warnings=warnings,
                ).extract()
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
            with metrics.stage("ancillary"):
                ancillary = AncillaryParser(
                    package,
                    styles,
                    opts,
                    warnings,
                    relationships=relationships,
                    asset_lookup=asset_lookup,
                    object_lookup=object_lookup,
                ).parse()
            with metrics.stage("style_debug_rows"):
                style_rows = styles.to_debug_list()

        # 单次遍历同时统计压缩/未压缩总大小，避免 zip_index 双重迭代。
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
            "sourcePath": str(docx_source) if not isinstance(docx_source, bytes) else "",
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
        )
        self._record_content_metrics(parsed, metrics)

        with metrics.stage("debug_write"), debug:
            self._write_debug_artifacts(
                debug, zip_index, content_types, relationships, style_rows, body_parser, parsed
            )
            parsed.metrics = metrics.snapshot()
            self._write_metrics_debug(debug, parsed)
        return parsed

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
            # 包结构：ZIP索引 + Content Types + Relationships 合并
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
            # 核心：解析后的正文块结构
            debug.write_json("blocks.json", parsed.blocks)
            # 资产与补充内容合并
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
            # 事件流
            debug.write_jsonl("events.jsonl", body_parser.body_events)
            # 警告与指标
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
                # 表格统计递归进入单元格，支持后续预算判断。
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
