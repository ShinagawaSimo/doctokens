"""解析 word/document.xml 正文 block。"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_BODY,
    _TAG_W_P,
    _TAG_W_PPR,
    _TAG_W_TBL,
    _TAG_W_TC,
    _TAG_W_TR,
    attr,
    child_elements,
    first_child,
    local_name,
    local_name_fast,
)
from ..core.models import ParseOptions, ParseWarning
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex
from ..ooxml.numbering import NumberingState
from ..ooxml.styles import StyleMap
from .inline import InlineParser


class BlockIdAllocator:
    """为正文 block 分配稳定的内部 ID。"""

    def __init__(self) -> None:
        self._next = 1

    def next(self) -> str:
        # 每篇文档独立计数，避免并发解析时共享状态。
        block_id = f"b{self._next}"
        self._next += 1
        return block_id


class DocumentBodyParser:
    """把 document.xml 的直接正文内容解析成段落、标题和表格。"""

    def __init__(
        self,
        package: PackageReader,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: dict[tuple[str, str], dict[str, Any]],
        object_lookup: dict[tuple[str, str], dict[str, Any]],
        numbering_state: NumberingState,
    ) -> None:
        self.package = package
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.numbering_state = numbering_state
        self.inline = InlineParser(
            styles=styles,
            options=options,
            warnings=warnings,
            relationships=relationships,
            asset_lookup=asset_lookup,
            object_lookup=object_lookup,
            on_page_break=self._mark_page_break,
        )
        self.ids = BlockIdAllocator()
        self._order = 0
        self._page_hint = 1
        # 计数器替代布尔：一个段落/表格内可能有多个 lastRenderedPageBreak。
        self._pending_page_breaks = 0
        self.body_events: list[dict[str, Any]] = []

    def parse(self) -> list[dict[str, Any]]:
        """流式解析 word/document.xml，并保持段落/表格的原始顺序。"""
        blocks: list[dict[str, Any]] = []
        with self.package.open_entry("word/document.xml") as stream:
            parser = ET.iterparse(stream, events=("start", "end"))
            stack: list[str] = []
            body_depth: int | None = None
            for event, elem in parser:
                # 优化：使用 local_name_fast 避免 split 内存分配。
                lname = local_name_fast(elem.tag)
                if event == "start":
                    # start 事件只维护当前位置栈，不构造完整 DOM。
                    stack.append(lname)
                    if lname == "body":
                        body_depth = len(stack)
                    continue

                direct_body_child = (
                    body_depth is not None
                    and len(stack) == body_depth + 1
                    and len(stack) >= 2
                    and stack[-2] == "body"
                )
                if direct_body_child and lname == "p":
                    # 只处理 body 直接段落，避免表格单元格内容被重复提升。
                    block = self.parse_paragraph(elem, "word/document.xml")
                    if block is not None:
                        blocks.append(block)
                    elem.clear()
                elif direct_body_child and lname == "tbl":
                    # 表格内可能有换页，parse_table 返回 list（每页一个子表 block）。
                    blocks.extend(self.parse_table(elem, "word/document.xml"))
                    elem.clear()
                elif direct_body_child and lname == "sectPr":
                    # 分节符：Word 渲染时总是从新页开始新节。
                    self._warn(
                        "SECTION_PAGE_BREAK",
                        "Section break treated as page break.",
                        part="word/document.xml",
                    )
                    self._pending_page_breaks += 1
                    elem.clear()

                if lname == "body":
                    body_depth = None
                stack.pop()
        for block in blocks:
            self._add_body_event(block)
        return blocks

    def parse_paragraph(self, p: ET.Element, part: str) -> dict[str, Any] | None:
        """解析段落；只有样式大纲级别明确时才输出 heading。"""
        block_id = self.ids.next()
        self._order += 1
        # 应用前一个 block（如表表格单元格）积累的断页数。
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0
        page_start = self._page_hint

        style_id = self._paragraph_style_id(p)
        runs, raw_hints = self.inline.paragraph_runs(p, part, block_id, style_id)
        numbering = self._paragraph_numbering(p, style_id, part, block_id)
        if numbering is not None:
            # 自动编号是 Word 可见文本，作为合成 run 放进正文流。
            runs.insert(0, {"text": numbering["text"], "kind": "numberingLabel"})
            raw_hints.append({"type": "numbering", **numbering})

        text = "".join(run["text"] for run in runs)
        if not text and not self.options.preserve_empty_paragraphs and not raw_hints:
            # 空段被过滤，但段内 lrpb 仍需推进页码。
            self._page_hint += self._pending_page_breaks
            self._pending_page_breaks = 0
            return None

        heading_level = self.styles.resolve_heading_level(style_id)
        block_type = "heading" if heading_level is not None else "paragraph"
        block: dict[str, Any] = {
            "id": block_id,
            "type": block_type,
            "part": part,
            "order": self._order,
            "page": page_start,
            "styleId": style_id,
            "text": text,
        }
        if heading_level is not None:
            # 标题只来自 styles.xml / outlineLvl，不从文本形态猜测。
            block["level"] = heading_level
            block["headingSource"] = "style"
        if numbering is not None:
            block["numbering"] = numbering
        if self.options.include_runs:
            block["runs"] = runs
        if self.options.include_raw_hints and raw_hints:
            block["rawHints"] = raw_hints
        # lrpb 标志本段内的分页，推进页码供后续 block 使用。
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0
        return block

    def parse_table(self, tbl: ET.Element, part: str) -> list[dict[str, Any]]:
        """解析 Word 表格，保留行列、合并单元格和单元格内 block。
        表格内发生换页时拆分为多个 block，使渲染器能在子表间输出 <page n=N>。
        同一行内多个单元格的 lrpb 合并为一次换页判断（按 _page_hint 变化）。"""
        self._order += 1
        # 应用前一个 block 积累的断页数。
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0

        sub_tables: list[dict[str, Any]] = []
        current_rows: list[dict[str, Any]] = []
        current_page = self._page_hint
        max_col = 0
        # 记录处理本行之前的页码，用于判断本行是否触发了换页。
        page_before_row = self._page_hint

        for row_index, tr in enumerate(child_elements(tbl, "w", "tr")):
            cells: list[dict[str, Any]] = []
            col_index = 0
            is_header = first_child(first_child(tr, "w", "trPr"), "w", "tblHeader") is not None
            for tc in child_elements(tr, "w", "tc"):
                # Word 表格不是简单二维数组，必须记录 colSpan/vMerge 信息。
                col_span = self._cell_col_span(tc)
                v_merge = self._cell_v_merge(tc)
                cell_blocks = self._parse_cell_blocks(tc, part)
                text = self._blocks_text(cell_blocks)
                cell: dict[str, Any] = {
                    "rowIndex": row_index,
                    "colIndex": col_index,
                    "rowSpan": 1,
                    "colSpan": col_span,
                    "text": text,
                    "blocks": cell_blocks,
                }
                if v_merge:
                    cell["vMerge"] = v_merge
                cells.append(cell)
                col_index += col_span
            max_col = max(max_col, col_index)
            row: dict[str, Any] = {"rowIndex": row_index, "cells": cells}
            if is_header:
                # 重复表头对 LLM 理解表格语义有帮助，保留成轻量标记。
                row["isHeader"] = True

            # 本行处理后 _page_hint 是否变化？同一行多列 lrpb 只算一次换页。
            if self._page_hint != page_before_row:
                if current_rows:
                    sub_tables.append(self._make_table_block(
                        part, current_page, current_rows, max_col
                    ))
                    current_rows = []
                # 同一行多单元格 lrpb 合并为一次换页：页码只 +1。
                self._page_hint = page_before_row + 1
                self._pending_page_breaks = 0
                current_page = self._page_hint

            current_rows.append(row)
            page_before_row = self._page_hint

        # 提交最后一批行。
        if current_rows:
            self._apply_vertical_merges(current_rows)
            sub_tables.append(self._make_table_block(
                part, current_page, current_rows, max_col
            ))

        return sub_tables

    def _make_table_block(
        self, part: str, page: int, rows: list[dict[str, Any]], max_col: int
    ) -> dict[str, Any]:
        """构造一个表格 block 字典。"""
        block_id = self.ids.next()
        return {
            "id": block_id,
            "type": "table",
            "part": part,
            "order": self._order,
            "page": page,
            "rows": rows,
            "columnCount": max_col,
        }

    def _parse_cell_blocks(self, tc: ET.Element, part: str) -> list[dict[str, Any]]:
        """解析单元格内部内容；单元格可以包含段落和嵌套表格。
        优化：使用预计算标签名直接比对，避免每次调用 local_name。"""
        blocks: list[dict[str, Any]] = []
        for child in tc:
            child_tag = child.tag
            if child_tag == _TAG_W_P:
                # 单元格段落保留为嵌套 block，避免丢失多段结构。
                block = self.parse_paragraph(child, part)
                if block is not None:
                    blocks.append(block)
            elif child_tag == _TAG_W_TBL:
                # 嵌套表格递归解析，表内换页也会拆分为多个子表。
                blocks.extend(self.parse_table(child, part))
        return blocks

    def _apply_vertical_merges(self, rows: list[dict[str, Any]]) -> None:
        """根据 vMerge 为合并起点补充 rowSpan。"""
        active: dict[int, dict[str, Any]] = {}
        for row in rows:
            for cell in row["cells"]:
                columns = range(cell["colIndex"], cell["colIndex"] + cell["colSpan"])
                v_merge = cell.get("vMerge")
                if v_merge == "restart":
                    # restart 单元格成为后续 continue 单元格的纵向合并起点。
                    for column in columns:
                        active[column] = cell
                elif v_merge == "continue":
                    # continue 单元格推动起点 rowSpan，仍保留自身位置便于还原网格。
                    origins: list[dict[str, Any]] = []
                    for column in columns:
                        origin = active.get(column)
                        if origin is not None and origin not in origins:
                            origins.append(origin)
                    for origin in origins:
                        origin["rowSpan"] += 1
                else:
                    # 非纵向合并单元格会截断同列上一个活动合并。
                    for column in columns:
                        active.pop(column, None)

    def _paragraph_style_id(self, p: ET.Element) -> str | None:
        """读取段落样式 ID。"""
        ppr = first_child(p, "w", "pPr")
        pstyle = first_child(ppr, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _paragraph_numbering(
        self, p: ET.Element, style_id: str | None, part: str, block_id: str
    ) -> dict | None:
        """读取段落编号，并推进编号计数器。"""
        ppr = first_child(p, "w", "pPr")
        numpr = first_child(ppr, "w", "numPr")
        style_numbering = self.styles.resolve_numbering(style_id)
        direct_num_id, direct_level = self._num_pr_values(numpr)

        if direct_num_id == "0":
            # numId=0 在 Word 中表示取消编号，也不回退到样式编号。
            return None
        num_id = direct_num_id or (style_numbering[0] if style_numbering else None)
        if num_id is None:
            return None
        level = direct_level if direct_level is not None else (
            style_numbering[1] if style_numbering else 0
        )
        return self.numbering_state.advance(num_id, level, part=part, block_id=block_id)

    def _num_pr_values(self, numpr: ET.Element | None) -> tuple[str | None, int | None]:
        """读取 w:numPr 中的 numId 和 ilvl。"""
        if numpr is None:
            return (None, None)
        num_id_node = first_child(numpr, "w", "numId")
        ilvl_node = first_child(numpr, "w", "ilvl")
        num_id = attr(num_id_node, "w", "val") if num_id_node is not None else None
        ilvl_raw = attr(ilvl_node, "w", "val") if ilvl_node is not None else None
        if ilvl_raw is None:
            return (num_id, None)
        try:
            return (num_id, int(ilvl_raw))
        except ValueError:
            # 非法层级不应中断解析，按 0 层处理并记录 warning。
            self._warn(
                "INVALID_PARAGRAPH_NUMBERING_LEVEL",
                f"Invalid paragraph numbering level: {ilvl_raw!r}",
                part="word/document.xml",
            )
            return (num_id, 0)

    def _cell_col_span(self, tc: ET.Element) -> int:
        """读取横向合并列数。"""
        tcpr = first_child(tc, "w", "tcPr")
        grid_span = first_child(tcpr, "w", "gridSpan")
        val = attr(grid_span, "w", "val") if grid_span is not None else None
        if val is None:
            return 1
        try:
            return max(1, int(val))
        except ValueError:
            # 非法 gridSpan 不应中断整篇文档解析。
            self._warn(
                "INVALID_GRID_SPAN",
                f"Invalid gridSpan value: {val!r}",
                part="word/document.xml",
            )
            return 1

    def _cell_v_merge(self, tc: ET.Element) -> str | None:
        """读取纵向合并标记。"""
        tcpr = first_child(tc, "w", "tcPr")
        vmerge = first_child(tcpr, "w", "vMerge")
        if vmerge is None:
            return None
        return attr(vmerge, "w", "val") or "continue"

    def _blocks_text(self, blocks: list[dict[str, Any]]) -> str:
        """把单元格内嵌 block 合并为单元格可读文本。"""
        parts: list[str] = []
        for block in blocks:
            if block["type"] in {"paragraph", "heading"}:
                if block["text"]:
                    parts.append(block["text"])
            elif block["type"] == "table":
                for row in block["rows"]:
                    cell_text = " | ".join(cell["text"] for cell in row["cells"])
                    if cell_text.strip():
                        parts.append(cell_text)
        return "\n".join(parts)

    def _add_body_event(self, block: dict[str, Any]) -> None:
        """记录 debug 用 body 事件，不影响最终 LLM 输出。"""
        event = {
            "id": block["id"],
            "type": block["type"],
            "order": block["order"],
            "part": block["part"],
        }
        if "text" in block:
            event["textPreview"] = block["text"][:120]
        if "numbering" in block:
            event["numberingLabel"] = block["numbering"]["label"]
        if block["type"] == "heading":
            event["level"] = block["level"]
        if block["type"] == "table":
            event["rowCount"] = len(block["rows"])
            event["columnCount"] = block["columnCount"]
        self.body_events.append(event)

    def _mark_page_break(self) -> None:
        """由 InlineParser 通知发现 lrpb/手动分页符，递增待处理断页计数。"""
        self._pending_page_breaks += 1

    def _warn(
        self,
        code: str,
        message: str,
        part: str | None = None,
        block_id: str | None = None,
    ) -> None:
        """追加解析 warning。"""
        self.warnings.append(
            ParseWarning(
                level="warning",
                code=code,
                message=message,
                part=part,
                block_id=block_id,
            )
        )
