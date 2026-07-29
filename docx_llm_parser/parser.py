"""解析流程编排入口。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core.debug import DebugWriter
from .core.metrics import MetricsRecorder
from .core.models import ParsedDocument, ParseOptions, ParseWarning
from .core.package import PackageReader
from .core.relationships import RelationshipIndex
from .extractors.ancillary import AncillaryParser
from .extractors.assets import AssetExtractor
from .extractors.body import DocumentBodyParser
from .extractors.objects import EmbeddedObjectExtractor
from .ooxml.numbering import NumberingParser, NumberingState
from .ooxml.styles import StylesParser

PARSER_VERSION = "0.1.0"


class DocxParser:
    """对外暴露的 DOCX 解析器。"""

    def parse(self, docx_path: str | Path, options: ParseOptions | None = None) -> ParsedDocument:
        """解析单个 DOCX；每次调用都创建独立上下文，便于并发。"""
        path = Path(docx_path)
        opts = options or ParseOptions(output_dir=Path("out") / path.stem)
        warnings: list[ParseWarning] = []
        output_dir = opts.output_dir
        debug_dir = output_dir / ".debug"
        debug = DebugWriter(debug_dir, enabled=opts.debug)
        # 优化：开启异步 debug 写入，JSON 序列化和磁盘 I/O 在后台线程完成。
        debug.enable_async()
        metrics = MetricsRecorder()
        metrics.set_counter("inputBytes", path.stat().st_size)

        with PackageReader(path, opts) as package:
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
                    output_dir=output_dir,
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

        package_info = {
            "entryCount": len(zip_index),
            "totalUncompressedBytes": sum(item["uncompressedSize"] for item in zip_index),
            "totalCompressedBytes": sum(item["compressedSize"] for item in zip_index),
        }
        metrics.set_counter("entryCount", package_info["entryCount"])
        metrics.set_counter("zipUncompressedBytes", package_info["totalUncompressedBytes"])
        metrics.set_counter("zipCompressedBytes", package_info["totalCompressedBytes"])
        metadata: dict[str, Any] = {
            "sourceFile": path.name,
            "sourcePath": str(path),
            "format": "docx",
            "parser": "docx_llm_parser",
            "parserVersion": PARSER_VERSION,
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
        parsed.metrics = metrics.snapshot()

        with metrics.stage("debug_write"):
            self._write_debug(
                debug, zip_index, content_types, relationships, style_rows, body_parser, parsed
            )
        # 等待异步 debug 写入全部完成，确保数据落盘后再写 metrics。
        debug.wait_all()
        parsed.metrics = metrics.snapshot()
        self._write_metrics_debug(debug, parsed)
        # 等待 metrics 异步写入完成后返回。
        debug.wait_all()
        return parsed

    def _write_debug(
        self,
        debug: DebugWriter,
        zip_index: list[dict[str, Any]],
        content_types: dict[str, Any],
        relationships: RelationshipIndex,
        style_rows: list[dict[str, Any]],
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
                    level="warning",
                    code="DEBUG_WRITE_FAILED",
                    message=f"Failed to write debug artifacts: {exc}",
                )
            )

    def _record_content_metrics(
        self, parsed: ParsedDocument, metrics: MetricsRecorder
    ) -> None:
        """统计输出预算和性能判断需要的节点数量。"""
        stats = self._block_stats(parsed.blocks)
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

    def _block_stats(self, blocks: list[dict[str, Any]]) -> dict[str, int]:
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
            block_type = block["type"]
            if block_type == "paragraph":
                stats["paragraphCount"] += 1
                stats["runCount"] += len(block.get("runs", []))
            elif block_type == "heading":
                stats["headingCount"] += 1
                stats["runCount"] += len(block.get("runs", []))
            elif block_type == "table":
                # 表格统计递归进入单元格，支持后续预算判断。
                stats["tableCount"] += 1
                stats["maxTableRows"] = max(stats["maxTableRows"], len(block["rows"]))
                stats["maxTableCols"] = max(stats["maxTableCols"], block["columnCount"])
                for row in block["rows"]:
                    stats["tableCellCount"] += len(row["cells"])
                    for cell in row["cells"]:
                        child_stats = self._block_stats(cell["blocks"])
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
                    level="warning",
                    code="METRICS_WRITE_FAILED",
                    message=f"Failed to write metrics debug artifact: {exc}",
                )
            )
