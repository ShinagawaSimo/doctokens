"""解析 word/document.xml 正文 block。"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_W_PARAGRAPH,
    _TAG_W_TABLE,
    attr,
    child_elements,
    first_child,
    local_name,
)
from ..core.models import (
    AssetLookup,
    Block,
    BodyEvent,
    NumberingLabel,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
)
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
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup,
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
        self._table_index = 0
        self._page_hint = 1
        # 计数器替代布尔：一个段落/表格内可能有多个 lastRenderedPageBreak。
        self._pending_page_breaks = 0
        self.body_events: list[BodyEvent] = []

    def parse(self) -> list[Block]:
        """流式解析 word/document.xml，并保持段落/表格的原始顺序。"""
        blocks: list[Block] = []
        with self.package.open_entry("word/document.xml") as stream:
            parser = ET.iterparse(stream, events=("start", "end"))
            stack: list[str] = []
            body_depth: int | None = None
            for event, elem in parser:
                # 优化：使用 local_name 避免 split 内存分配。
                lname = local_name(elem.tag)
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
        for parsed_block in blocks:
            self._add_body_event(parsed_block)
        return blocks

    def parse_paragraph(self, p: ET.Element, part: str) -> TextBlock | None:
        """解析段落；只有样式大纲级别明确时才输出 heading。"""
        block_id = self.ids.next()
        self._order += 1
        # 应用前一个 block 积累的断页数。
        page_start = self._flush_pending_page_breaks()

        style_id = self._paragraph_style_id(p)
        runs, raw_hints = self.inline.paragraph_runs(p, part, block_id, style_id)
        numbering = self._paragraph_numbering(p, style_id, part, block_id)
        if numbering is not None:
            # 自动编号是 Word 可见文本，作为合成 run 放进正文流。
            runs.insert(0, {"text": numbering["text"], "kind": "numberingLabel"})
            raw_hints.append({"type": "numbering", **numbering})

        # 单次遍历同时收集文本和检测内联对象，避免热路径双重迭代。
        text_parts: list[str] = []
        has_objects = False
        for run in runs:
            text_parts.append(run["text"])
            if "objects" in run:
                has_objects = True
        text = "".join(text_parts)
        # text.isspace() 避免 text.strip() 创建新字符串的开销。
        if (
            (not text or text.isspace())
            and not has_objects
            and not self.options.preserve_empty_paragraphs
        ):
            # 空段（无可见文本、无内联对象）不产生内容。
            # 段内 lrpb/手动分页在 Word 渲染中无视觉效果，一并丢弃，不推进页码。
            self._pending_page_breaks = 0
            return None

        # 段内 lrpb/手动分页推进本段起始页码。
        page_start += self._pending_page_breaks
        self._page_hint = page_start
        self._pending_page_breaks = 0

        heading_level = self.styles.resolve_heading_level(style_id)
        if heading_level is not None:
            # 标题只来自 styles.xml / outlineLvl，不从文本形态猜测。
            block: TextBlock = {
                "id": block_id,
                "type": "heading",
                "part": part,
                "order": self._order,
                "page": page_start,
                "styleId": style_id,
                "text": text,
                "level": heading_level,
                "headingSource": "style",
            }
        else:
            block = {
                "id": block_id,
                "type": "paragraph",
                "part": part,
                "order": self._order,
                "page": page_start,
                "styleId": style_id,
                "text": text,
            }
        if numbering is not None:
            block["numbering"] = numbering
        if self.options.include_runs:
            block["runs"] = runs
        if self.options.include_raw_hints and raw_hints:
            block["rawHints"] = raw_hints
        return block

    def parse_table(self, tbl: ET.Element, part: str) -> list[TableBlock]:
        """解析 Word 表格，保留行列、合并单元格和单元格内 block。
        表格内发生换页时拆分为多个 block，使渲染器能在子表间输出 <page n=N>。
        同一行内多个单元格的 lrpb 合并为一次换页判断（按 _page_hint 变化）。"""
        self._order += 1
        table_id = self._next_table_id()
        # 应用前一个 block 积累的断页数。
        current_page = self._flush_pending_page_breaks()

        sub_tables: list[TableBlock] = []
        current_rows: list[TableRow] = []
        max_col = 0
        # 记录处理本行之前的页码，用于判断本行是否触发了换页。
        page_before_row = self._page_hint

        for row_index, tr in enumerate(child_elements(tbl, "w", "tr")):
            cells: list[TableCell] = []
            col_index = 0
            is_header = first_child(first_child(tr, "w", "trPr"), "w", "tblHeader") is not None
            for tc in child_elements(tr, "w", "tc"):
                # Word 表格不是简单二维数组，必须记录 colSpan/vMerge 信息。
                col_span = self._cell_col_span(tc)
                v_merge = self._cell_v_merge(tc)
                cell_blocks = self._parse_cell_blocks(tc, part)
                text = self._blocks_text(cell_blocks)
                cell: TableCell = {
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
            row: TableRow = {"rowIndex": row_index, "cells": cells}
            if is_header:
                # 重复表头对 LLM 理解表格语义有帮助，保留成轻量标记。
                row["isHeader"] = True

            # 本行处理后 _page_hint 是否变化？同一行多列 lrpb 只算一次换页。
            if self._page_hint != page_before_row:
                if current_rows:
                    sub_tables.append(
                        self._make_table_block(
                            part,
                            current_page,
                            current_rows,
                            max_col,
                            table_id,
                            len(sub_tables) + 1,
                        )
                    )
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
            sub_tables.append(
                self._make_table_block(
                    part,
                    current_page,
                    current_rows,
                    max_col,
                    table_id,
                    len(sub_tables) + 1,
                )
            )

        return sub_tables

    def _make_table_block(
        self,
        part: str,
        page: int,
        rows: list[TableRow],
        max_col: int,
        table_id: str,
        segment_index: int,
    ) -> TableBlock:
        """构造一个表格 block 字典。"""
        block_id = self.ids.next()
        return {
            "id": block_id,
            "type": "table",
            "part": part,
            "order": self._order,
            "page": page,
            "tableId": table_id,
            "segmentIndex": segment_index,
            "rows": rows,
            "columnCount": max_col,
        }

    def _next_table_id(self) -> str:
        """Allocate a stable document-order ID for one logical table."""
        self._table_index += 1
        return f"t{self._table_index}"

    def _parse_cell_blocks(self, tc: ET.Element, part: str) -> list[Block]:
        """解析单元格内部内容；单元格可以包含段落和嵌套表格。
        优化：使用预计算标签名直接比对，避免每次调用 local_name。"""
        blocks: list[Block] = []
        for child in tc:
            child_tag = child.tag
            if child_tag == _TAG_W_PARAGRAPH:
                # 单元格段落保留为嵌套 block，避免丢失多段结构。
                block = self.parse_paragraph(child, part)
                if block is not None:
                    blocks.append(block)
            elif child_tag == _TAG_W_TABLE:
                # 嵌套表格递归解析，表内换页也会拆分为多个子表。
                blocks.extend(self.parse_table(child, part))
        return blocks

    def _apply_vertical_merges(self, rows: list[TableRow]) -> None:
        """根据 vMerge 为合并起点补充 rowSpan。"""
        active: dict[int, TableCell] = {}
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
                    origins: list[TableCell] = []
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
        paragraph_properties = first_child(p, "w", "pPr")
        pstyle = first_child(paragraph_properties, "w", "pStyle")
        return attr(pstyle, "w", "val") if pstyle is not None else None

    def _paragraph_numbering(
        self, p: ET.Element, style_id: str | None, part: str, block_id: str
    ) -> NumberingLabel | None:
        """读取段落编号，并推进编号计数器。"""
        paragraph_properties = first_child(p, "w", "pPr")
        numbering_properties = first_child(paragraph_properties, "w", "numPr")
        style_numbering = self.styles.resolve_numbering(style_id)
        direct_num_id, direct_level = self._num_pr_values(numbering_properties)

        if direct_num_id == "0":
            # numId=0 在 Word 中表示取消编号，也不回退到样式编号。
            return None
        num_id = direct_num_id or (style_numbering[0] if style_numbering else None)
        if num_id is None:
            return None
        level = (
            direct_level
            if direct_level is not None
            else (style_numbering[1] if style_numbering else 0)
        )
        return self.numbering_state.advance(num_id, level, part=part, block_id=block_id)

    def _num_pr_values(
        self, numbering_properties: ET.Element | None
    ) -> tuple[str | None, int | None]:
        """读取 w:numPr 中的 numId 和 ilvl。"""
        if numbering_properties is None:
            return (None, None)
        num_id_node = first_child(numbering_properties, "w", "numId")
        ilvl_node = first_child(numbering_properties, "w", "ilvl")
        num_id = attr(num_id_node, "w", "val") if num_id_node is not None else None
        level_str = attr(ilvl_node, "w", "val") if ilvl_node is not None else None
        if level_str is None:
            return (num_id, None)
        try:
            return (num_id, int(level_str))
        except ValueError:
            # 非法层级不应中断解析，按 0 层处理并记录 warning。
            self._warn(
                "INVALID_PARAGRAPH_NUMBERING_LEVEL",
                f"Invalid paragraph numbering level: {level_str!r}",
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

    def _blocks_text(self, blocks: list[Block]) -> str:
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

    def _add_body_event(self, block: Block) -> None:
        """记录 debug 用 body 事件，不影响最终 LLM 输出。"""
        event: BodyEvent = {
            "id": block["id"],
            "type": block["type"],
            "order": block["order"],
            "part": block["part"],
        }
        if block["type"] in {"paragraph", "heading"}:
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

    def _flush_pending_page_breaks(self) -> int:
        """应用积累的断页并返回当前页码。"""
        self._page_hint += self._pending_page_breaks
        self._pending_page_breaks = 0
        return self._page_hint

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
