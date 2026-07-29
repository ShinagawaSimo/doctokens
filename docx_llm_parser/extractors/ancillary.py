"""解析页眉页脚、脚注尾注和批注等补充内容。"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_P,
    _TAG_W_PPR,
    _TAG_W_P_STYLE,
    _TAG_W_SDT,
    _TAG_W_SDT_CONTENT,
    _TAG_W_SMART_TAG,
    _TAG_W_TBL,
    _TAG_W_TC,
    _TAG_W_TR,
    attr,
    child_elements,
    first_child,
    local_name_fast,
)
from ..core.models import ParseOptions, ParseWarning
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.styles import StyleMap
from .inline import InlineParser


class AncillaryParser:
    """解析 body 之外但对 LLM 理解仍有价值的内容。"""

    def __init__(
        self,
        package: PackageReader,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: dict[tuple[str, str], dict[str, Any]],
        object_lookup: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        self.package = package
        self.options = options
        self.warnings = warnings
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
        )
        self._block_index = 0

    def parse(self) -> dict[str, list[dict]]:
        """返回 headers/footers/footnotes/endnotes/comments 五类补充信息。"""
        return {
            "headers": self._parse_header_footer("header"),
            "footers": self._parse_header_footer("footer"),
            "footnotes": self._parse_notes("word/footnotes.xml", "footnote"),
            "endnotes": self._parse_notes("word/endnotes.xml", "endnote"),
            "comments": self._parse_comments(),
        }

    def _parse_header_footer(self, kind: str) -> list[dict]:
        """解析 word/header*.xml 或 word/footer*.xml。"""
        prefix = f"word/{kind}"
        rows: list[dict] = []
        for name in sorted(item["name"] for item in self.package.read_entry_index()):
            if not (name.startswith(prefix) and name.endswith(".xml")):
                continue
            root = self._parse_xml_part(name)
            if root is None:
                continue
            content = self._container_content(root, name)
            if content["text"].strip() or self._has_objects(content["runs"]):
                item_id = name.rsplit("/", 1)[-1].removesuffix(".xml")
                row = {
                    "id": item_id,
                    "loc": f"{kind}s.{item_id}",
                    "text": content["text"],
                    "runs": content["runs"],
                }
                if self.options.include_raw_hints and content["rawHints"]:
                    row["rawHints"] = content["rawHints"]
                rows.append(row)
        return rows

    def _parse_notes(self, part_name: str, tag_name: str) -> list[dict]:
        """解析脚注或尾注。"""
        if not self.package.exists(part_name):
            return []
        root = self._parse_xml_part(part_name)
        if root is None:
            return []
        rows: list[dict] = []
        group = "footnotes" if tag_name == "footnote" else "endnotes"
        for note in child_elements(root, "w", tag_name):
            note_type = attr(note, "w", "type")
            if note_type in {"separator", "continuationSeparator"}:
                # 分隔线不是用户内容。
                continue
            note_id = attr(note, "w", "id")
            content = self._container_content(note, part_name)
            if content["text"].strip() or self._has_objects(content["runs"]):
                row = {
                    "id": note_id,
                    "loc": f"{group}.{note_id}",
                    "text": content["text"],
                    "runs": content["runs"],
                }
                if self.options.include_raw_hints and content["rawHints"]:
                    row["rawHints"] = content["rawHints"]
                rows.append(row)
        return rows

    def _parse_comments(self) -> list[dict]:
        """解析批注正文。"""
        part_name = "word/comments.xml"
        if not self.package.exists(part_name):
            return []
        root = self._parse_xml_part(part_name)
        if root is None:
            return []
        rows: list[dict] = []
        for comment in child_elements(root, "w", "comment"):
            comment_id = attr(comment, "w", "id")
            content = self._container_content(comment, part_name)
            if content["text"].strip() or self._has_objects(content["runs"]):
                row = {
                    "id": comment_id,
                    "loc": f"comments.{comment_id}",
                    "author": attr(comment, "w", "author"),
                    "date": attr(comment, "w", "date"),
                    "text": content["text"],
                    "runs": content["runs"],
                }
                if self.options.include_raw_hints and content["rawHints"]:
                    row["rawHints"] = content["rawHints"]
                rows.append(row)
        return rows

    def _parse_xml_part(self, part_name: str) -> ET.Element | None:
        """读取 XML part；失败时记录 warning 并继续。"""
        try:
            with self.package.open_entry(part_name) as stream:
                return ET.parse(stream).getroot()
        except Exception as exc:
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="ANCILLARY_XML_PARSE_FAILED",
                    message=f"Failed to parse {part_name}: {exc}",
                    part=part_name,
                )
            )
            return None

    def _container_content(self, node: ET.Element, part: str) -> dict[str, Any]:
        """提取容器内段落、表格和轻量 inline 对象。
        优化：使用预计算标签名直接比对，避免热路径中的 qn()/local_name 调用。"""
        text_parts: list[str] = []
        runs: list[dict[str, Any]] = []
        raw_hints: list[dict[str, Any]] = []
        for child in node:
            child_tag = child.tag
            if child_tag == _TAG_W_P:
                # 补充区域也按段落解析，避免丢失链接和格式。
                p_runs, p_hints = self.inline.paragraph_runs(
                    child, part, self._next_block_id(part), self._paragraph_style_id(child)
                )
                p_text = "".join(run["text"] for run in p_runs)
                if p_text.strip() or self._has_objects(p_runs):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(p_runs)
                    text_parts.append(p_text)
                    raw_hints.extend(p_hints)
            elif child_tag == _TAG_W_TBL:
                # 补充区域内表格压缩为行文本，但保留单元格里的 inline 对象。
                table_content = self._table_content(child, part)
                if table_content["text"].strip() or self._has_objects(table_content["runs"]):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(table_content["runs"])
                    text_parts.append(table_content["text"])
                    raw_hints.extend(table_content["rawHints"])
            elif child_tag in (_TAG_W_SDT, _TAG_W_SDT_CONTENT, _TAG_W_SMART_TAG):
                # 包装层继续向内提取可读内容。
                nested = self._container_content(child, part)
                if nested["text"].strip() or self._has_objects(nested["runs"]):
                    if runs:
                        runs.append({"text": "\n"})
                    runs.extend(nested["runs"])
                    text_parts.append(nested["text"])
                    raw_hints.extend(nested["rawHints"])
        return {"text": "\n".join(text_parts), "runs": runs, "rawHints": raw_hints}

    def _table_content(self, tbl: ET.Element, part: str) -> dict[str, Any]:
        """把补充区域中的表格压缩为行文本，并保留 inline run。"""
        text_rows: list[str] = []
        runs: list[dict[str, Any]] = []
        raw_hints: list[dict[str, Any]] = []
        for tr in child_elements(tbl, "w", "tr"):
            cell_contents = [
                self._container_content(tc, part) for tc in child_elements(tr, "w", "tc")
            ]
            visible_cells = [
                cell for cell in cell_contents if cell["text"].strip() or self._has_objects(cell["runs"])
            ]
            if not visible_cells:
                continue
            if runs:
                runs.append({"text": "\n"})
            row_texts: list[str] = []
            for cell_index, cell in enumerate(visible_cells):
                if cell_index:
                    runs.append({"text": " | "})
                runs.extend(cell["runs"])
                row_texts.append(cell["text"].strip())
                raw_hints.extend(cell["rawHints"])
            text_rows.append(" | ".join(text for text in row_texts if text))
        return {"text": "\n".join(text_rows), "runs": runs, "rawHints": raw_hints}

    def _paragraph_style_id(self, p: ET.Element) -> str | None:
        """读取补充区域段落样式 ID。"""
        ppr = first_child(p, "w", "pPr")
        pstyle = first_child(ppr, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _next_block_id(self, part: str) -> str:
        """为 supplemental inline warning 生成轻量定位 ID。"""
        self._block_index += 1
        return f"{part}#{self._block_index}"

    def _has_objects(self, runs: list[dict[str, Any]]) -> bool:
        """判断 run 流中是否有图片、脚注引用、公式等非文本对象。"""
        return any("objects" in run for run in runs)
