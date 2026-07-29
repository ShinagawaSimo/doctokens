"""解析 word/styles.xml，并根据样式识别标题层级。"""

from __future__ import annotations

from dataclasses import asdict
from xml.etree import ElementTree as ET

from ..core.constants import attr, first_child, qn
from ..core.models import ParseWarning, StyleRecord
from ..core.package import PackageReader
from .formatting import merge_run_formats, parse_run_format


class StyleMap:
    """样式索引；构建完成后只读，便于并发解析。"""

    def __init__(self, records: dict[str, StyleRecord], warnings: list[ParseWarning]) -> None:
        self.records = records
        self.warnings = warnings
        self._heading_level_cache: dict[str, int | None] = {}
        self._numbering_cache: dict[str, tuple[str, int] | None] = {}
        self._run_format_cache: dict[str, dict] = {}

    def resolve_heading_level(self, style_id: str | None) -> int | None:
        """根据 styleId 解析标题级别；不使用段落文本启发式。"""
        if not style_id:
            return None
        if style_id not in self._heading_level_cache:
            # 样式继承链只解析一次，后续 run/段落热路径直接读缓存。
            self._heading_level_cache[style_id] = self._resolve_heading_level(
                style_id, visited=set()
            )
        return self._heading_level_cache[style_id]

    def resolve_numbering(self, style_id: str | None) -> tuple[str, int] | None:
        """根据 styleId 解析样式明确绑定的编号信息。"""
        if not style_id:
            return None
        if style_id not in self._numbering_cache:
            # 编号样式继承同样缓存，避免每个段落重复递归。
            self._numbering_cache[style_id] = self._resolve_numbering(style_id, visited=set())
        return self._numbering_cache[style_id]

    def resolve_run_format(self, style_id: str | None) -> dict:
        """根据 styleId 解析样式继承后的可见文字格式。"""
        if not style_id:
            return {}
        if style_id not in self._run_format_cache:
            # run 数量通常远多于样式数量，缓存能明显降低大文档重复计算。
            self._run_format_cache[style_id] = self._resolve_run_format(style_id, visited=set())
        return self._run_format_cache[style_id]

    def to_debug_list(self) -> list[dict]:
        """输出 debug 用样式摘要。"""
        rows: list[dict] = []
        for style_id in sorted(self.records):
            record = self.records[style_id]
            record.resolved_heading_level = self.resolve_heading_level(style_id)
            rows.append(asdict(record))
        return rows

    def _resolve_heading_level(self, style_id: str, visited: set[str]) -> int | None:
        """递归解析 basedOn 继承链中的 outline level。"""
        if style_id in visited:
            # 样式循环继承不能递归到底，记录 warning 后停止。
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="STYLE_INHERITANCE_CYCLE",
                    message=f"Style inheritance cycle detected at {style_id}",
                    part="word/styles.xml",
                )
            )
            return None

        record = self.records.get(style_id)
        if record is None:
            # 样式表里没有明确记录时，不做任何标题 fallback。
            return None

        if record.outline_level is not None:
            # OOXML outlineLvl 是 0 基，输出给 LLM 使用 1 基。
            return record.outline_level + 1

        if record.based_on:
            # 只沿继承链查找明确的 outlineLvl，不根据样式名称猜测。
            visited.add(style_id)
            return self._resolve_heading_level(record.based_on, visited)
        return None

    def _resolve_numbering(self, style_id: str, visited: set[str]) -> tuple[str, int] | None:
        """递归解析 basedOn 继承链中的 numPr。"""
        if style_id in visited:
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="STYLE_NUMBERING_INHERITANCE_CYCLE",
                    message=f"Style numbering inheritance cycle detected at {style_id}",
                    part="word/styles.xml",
                )
            )
            return None

        record = self.records.get(style_id)
        if record is None:
            return None

        if record.numbering_num_id is not None:
            # 样式中的 numPr 是 Word 明确结构，不是按样式名称猜测。
            return (record.numbering_num_id, record.numbering_level or 0)

        if record.based_on:
            visited.add(style_id)
            return self._resolve_numbering(record.based_on, visited)
        return None

    def _resolve_run_format(self, style_id: str, visited: set[str]) -> dict:
        """递归合并 basedOn 继承链中的 run 格式。"""
        if style_id in visited:
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="STYLE_FORMAT_INHERITANCE_CYCLE",
                    message=f"Style format inheritance cycle detected at {style_id}",
                    part="word/styles.xml",
                )
            )
            return {}

        record = self.records.get(style_id)
        if record is None:
            return {}

        inherited: dict = {}
        if record.based_on:
            visited.add(style_id)
            inherited = self._resolve_run_format(record.based_on, visited)
        return merge_run_formats(inherited, record.run_format)


class StylesParser:
    """读取 styles.xml 并构建 StyleMap。"""

    def __init__(self, package: PackageReader, warnings: list[ParseWarning]) -> None:
        self.package = package
        self.warnings = warnings

    def parse(self) -> StyleMap:
        """解析样式文件；缺失时返回空样式表。"""
        if not self.package.exists("word/styles.xml"):
            # 样式文件缺失时仍可抽段落，但无法可靠识别标题。
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="MISSING_STYLES",
                    message="word/styles.xml is missing; heading detection will be limited.",
                    part="word/styles.xml",
                )
            )
            return StyleMap({}, self.warnings)

        with self.package.open_entry("word/styles.xml") as stream:
            root = ET.parse(stream).getroot()

        records: dict[str, StyleRecord] = {}
        for style in root.findall(qn("w", "style")):
            style_id = attr(style, "w", "styleId")
            if not style_id:
                # 没有 styleId 的样式无法被正文引用。
                continue
            record = StyleRecord(
                style_id=style_id,
                type=attr(style, "w", "type") or "unknown",
                is_default=(attr(style, "w", "default") or "").lower() in {"1", "true"},
            )
            name = first_child(style, "w", "name")
            based_on = first_child(style, "w", "basedOn")
            next_style = first_child(style, "w", "next")
            ppr = first_child(style, "w", "pPr")
            rpr = first_child(style, "w", "rPr")
            outline = first_child(ppr, "w", "outlineLvl")
            numpr = first_child(ppr, "w", "numPr")

            record.name = attr(name, "w", "val") if name is not None else None
            record.based_on = attr(based_on, "w", "val") if based_on is not None else None
            record.next = attr(next_style, "w", "val") if next_style is not None else None
            record.run_format = parse_run_format(rpr)
            outline_val = attr(outline, "w", "val") if outline is not None else None
            if outline_val is not None:
                try:
                    record.outline_level = int(outline_val)
                except ValueError:
                    # 非法 outlineLvl 不影响其它样式解析。
                    self.warnings.append(
                        ParseWarning(
                            level="warning",
                            code="INVALID_OUTLINE_LEVEL",
                            message=f"Invalid outline level {outline_val!r} for style {style_id}",
                            part="word/styles.xml",
                        )
                    )
            num_id_node = first_child(numpr, "w", "numId")
            ilvl_node = first_child(numpr, "w", "ilvl")
            num_id = attr(num_id_node, "w", "val") if num_id_node is not None else None
            ilvl = attr(ilvl_node, "w", "val") if ilvl_node is not None else None
            if num_id is not None:
                record.numbering_num_id = num_id
                try:
                    record.numbering_level = int(ilvl) if ilvl is not None else 0
                except ValueError:
                    # 样式编号层级非法时按 0 层处理，同时保留 warning。
                    record.numbering_level = 0
                    self.warnings.append(
                        ParseWarning(
                            level="warning",
                            code="INVALID_STYLE_NUMBERING_LEVEL",
                            message=f"Invalid numbering level {ilvl!r} for style {style_id}",
                            part="word/styles.xml",
                        )
                    )
            records[style_id] = record

        style_map = StyleMap(records, self.warnings)
        for record in records.values():
            record.resolved_heading_level = style_map.resolve_heading_level(record.style_id)
        return style_map
