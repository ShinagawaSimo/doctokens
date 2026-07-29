"""解析器内部数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParseOptions:
    """解析配置；设为不可变，避免并发任务互相污染。"""

    preserve_empty_paragraphs: bool = False
    include_runs: bool = True
    include_raw_hints: bool = True
    debug: bool = True
    revision_mode: str = "final"
    output_dir: Path = Path("out")
    max_zip_entries: int = 10000
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024


@dataclass
class ParseWarning:
    """解析过程中可恢复问题的记录。"""

    level: str
    code: str
    message: str
    part: str | None = None
    block_id: str | None = None


@dataclass
class RelationshipRecord:
    """OPC relationship 记录。"""

    source_part: str
    id: str
    type: str
    target: str
    target_mode: str | None = None
    resolved_target: str | None = None


@dataclass
class StyleRecord:
    """Word 样式摘要。"""

    style_id: str
    type: str = "unknown"
    name: str | None = None
    based_on: str | None = None
    next: str | None = None
    outline_level: int | None = None
    numbering_num_id: str | None = None
    numbering_level: int | None = None
    run_format: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    resolved_heading_level: int | None = None


@dataclass
class ParsedDocument:
    """内部完整解析结果；最终输出会再精简。"""

    metadata: dict[str, Any]
    package_info: dict[str, Any]
    blocks: list[dict[str, Any]]
    relationships: list[RelationshipRecord]
    styles: list[StyleRecord]
    warnings: list[ParseWarning]
    debug_dir: str | None = None
    content_types: dict[str, Any] = field(default_factory=dict)
    assets: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)
    smartarts: list[dict[str, Any]] = field(default_factory=list)
    headers: list[dict[str, Any]] = field(default_factory=list)
    footers: list[dict[str, Any]] = field(default_factory=list)
    footnotes: list[dict[str, Any]] = field(default_factory=list)
    endnotes: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    numbering: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """输出内部完整结构，主要供 debug 或开发检查使用。"""
        return {
            "metadata": self.metadata,
            "packageInfo": self.package_info,
            "blocks": self.blocks,
            "relationships": [asdict(item) for item in self.relationships],
            "styles": [asdict(item) for item in self.styles],
            "warnings": [asdict(item) for item in self.warnings],
            "debugDir": self.debug_dir,
            "contentTypes": self.content_types,
            "assets": self.assets,
            "charts": self.charts,
            "smartarts": self.smartarts,
            "headers": self.headers,
            "footers": self.footers,
            "footnotes": self.footnotes,
            "endnotes": self.endnotes,
            "comments": self.comments,
            "numbering": self.numbering,
            "metrics": self.metrics,
        }
