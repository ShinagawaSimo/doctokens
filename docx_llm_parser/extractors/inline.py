"""解析 WordprocessingML 段落内联内容。"""

from __future__ import annotations

from collections.abc import Callable
from xml.etree import ElementTree as ET

from ..core.constants import (
    _TAG_M_OMATH,
    _TAG_M_OMATH_PARA,
    _TAG_W_ANNOTATION_REF,
    _TAG_W_BREAK,
    _TAG_W_CARRIAGE_RETURN,
    _TAG_W_COMMENT_REFERENCE,
    _TAG_W_DELETION_TEXT,
    _TAG_W_DRAWING,
    _TAG_W_ENDNOTE_REF,
    _TAG_W_ENDNOTE_REFERENCE,
    _TAG_W_FLD_CHAR,
    _TAG_W_FOOTNOTE_REF,
    _TAG_W_FOOTNOTE_REFERENCE,
    _TAG_W_INSTR_TEXT,
    _TAG_W_LAST_RENDERED_PAGE_BREAK,
    _TAG_W_OBJECT,
    _TAG_W_PICTURE,
    _TAG_W_RUN_PROPERTIES,
    _TAG_W_RUN_STYLE,
    _TAG_W_TAB,
    _TAG_W_TEXT,
    attr,
    child_elements,
    first_child,
    local_name,
    qualified_name,
)
from ..core.models import (
    AssetLookup,
    Chart,
    DrawingCommon,
    InlineObject,
    LinkInfo,
    ObjectLookup,
    ParseOptions,
    ParseWarning,
    RawHint,
    Run,
    SmartArt,
)
from ..core.relationships import RelationshipIndex
from ..ooxml.formatting import merge_run_formats, parse_run_format, visible_run_format
from ..ooxml.omml_latex import omath_to_latex
from ..ooxml.styles import StyleMap

PageBreakCallback = Callable[[], None]


def _progid_to_type(progid: str) -> str:
    """Map OLE ProgID to a human-readable type name."""
    progid_lower = progid.lower()
    if "excel" in progid_lower:
        return "excel"
    if "word" in progid_lower:
        return "word"
    if "powerpoint" in progid_lower:
        return "powerpoint"
    if "acroexch" in progid_lower:
        return "pdf"
    if "visio" in progid_lower:
        return "visio"
    if "paint" in progid_lower:
        return "image"
    if "package" in progid_lower:
        return "package"
    return "unknown"


class InlineParser:
    """把段落内的文本、链接、格式和轻量对象解析成统一 run 流。"""

    def __init__(
        self,
        styles: StyleMap,
        options: ParseOptions,
        warnings: list[ParseWarning],
        relationships: RelationshipIndex,
        asset_lookup: AssetLookup,
        object_lookup: ObjectLookup | None = None,
        on_page_break: PageBreakCallback | None = None,
    ) -> None:
        self.styles = styles
        self.options = options
        self.warnings = warnings
        self.relationships = relationships
        self.asset_lookup = asset_lookup
        self.object_lookup = object_lookup or {}
        self.on_page_break = on_page_break

    def paragraph_runs(
        self,
        p: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
    ) -> tuple[list[Run], list[RawHint]]:
        """解析一个段落内的 run，并返回 debug 用 raw hints。"""
        runs: list[Run] = []
        raw_hints: list[RawHint] = []
        for child in p:
            self._extract_inline_runs(child, part, block_id, paragraph_style_id, raw_hints, runs)
        return runs, raw_hints

    def _extract_inline_runs(
        self,
        node: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
        runs: list[Run],
    ) -> None:
        """递归处理段落内联节点，保留 Word 明确给出的结构。"""
        # 优化：使用 local_name 避免 split 内存分配（热路径每秒数千次调用）。
        lname = local_name(node.tag)
        if lname == "pPr":
            # 段落属性由外层 block parser 处理。
            return
        if lname == "r":
            # run 是 Word 文本和内联对象的常用载体。
            run = self._parse_run(node, part, block_id, paragraph_style_id, raw_hints)
            if run["text"] or "objects" in run or self.options.preserve_empty_paragraphs:
                runs.append(run)
            return
        if lname == "hyperlink":
            # 超链接的显示文字复用普通 inline 解析，链接目标作为轻量属性附着。
            link = self._hyperlink_info(node, part)
            raw_hints.append({"type": "hyperlink", **link})
            temp_runs: list[Run] = []
            for child in node:
                self._extract_inline_runs(
                    child, part, block_id, paragraph_style_id, raw_hints, temp_runs
                )
            for run in temp_runs:
                run["link"] = link
                runs.append(run)
            return
        if lname == "ins":
            # 插入修订在 final/review 视图中属于可见文本。
            self._warn(
                "REVISION_INSERTION_INCLUDED",
                "Encountered insertion revision; parser includes inserted text "
                "in final/review mode.",
                part=part,
                block_id=block_id,
            )
            if self.options.revision_mode in {"final", "review"}:
                revision_runs: list[Run] = []
                for child in node:
                    self._extract_inline_runs(
                        child, part, block_id, paragraph_style_id, raw_hints, revision_runs
                    )
                for run in revision_runs:
                    if self.options.revision_mode == "review":
                        run["revision"] = "inserted"
                    runs.append(run)
            return
        if lname == "del":
            # 删除修订只在 original/review 视图中输出。
            self._warn(
                "REVISION_DELETION_SKIPPED",
                "Encountered deletion revision; deletion handling depends on revision_mode.",
                part=part,
                block_id=block_id,
            )
            if self.options.revision_mode in {"original", "review"}:
                text = "".join((item.text or "") for item in node.iter(_TAG_W_DELETION_TEXT))
                if text:
                    deletion_run: Run = {"text": text}
                    if self.options.revision_mode == "review":
                        deletion_run["revision"] = "deleted"
                    runs.append(deletion_run)
            return
        if lname in {"sdt", "sdtContent", "smartTag"}:
            # 内容控件和智能标记是包装层，继续读取内部可见内容。
            for child in node:
                self._extract_inline_runs(
                    child, part, block_id, paragraph_style_id, raw_hints, runs
                )
            return
        if lname in {"oMath", "oMathPara"}:
            # 段落级 OMML 公式作为轻量对象进入最终 XML。
            obj = self._equation_object(node)
            runs.append({"text": "", "objects": [obj]})
            raw_hints.append(obj)
            return
        if lname in {"bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd"}:
            # 这些标记不贡献可读文本。
            return
        if lname == "object":
            obj = self._parse_embedded_object(node)
            runs.append({"text": "", "objects": [obj]})
            raw_hints.append(obj)
            return
        if lname.startswith("commentRange"):
            # 批注范围本身不含正文，commentReference 和 comments.xml 负责关联。
            self._warn(
                "COMMENT_ANCHOR_UNSUPPORTED",
                "Encountered comment range marker; parser records commentReference when present.",
                part=part,
                block_id=block_id,
            )
            return
        self._warn(
            "UNSUPPORTED_PARAGRAPH_CHILD",
            f"Encountered unsupported paragraph child: {lname}",
            part=part,
            block_id=block_id,
        )

    def _parse_run(
        self,
        run: ET.Element,
        part: str,
        block_id: str,
        paragraph_style_id: str | None,
        raw_hints: list[RawHint],
    ) -> Run:
        """解析 run 的可见文本、必要格式和内联对象。
        优化：单次遍历 run 的所有子节点，按标签名分发处理。
        原来需要 first_child(run, 'rPr') + child 循环两次扫描，
        现在合并为一次迭代。"""
        text_parts: list[str] = []
        run_properties: ET.Element | None = None
        parsed_run: Run = {"text": ""}

        # 单次遍历：同时收集 rPr 和处理文本/对象子节点。
        for child in run:
            # 优化：使用预计算标签名比对，避免重复 qualified_name() 调用。
            child_tag = child.tag
            if child_tag == _TAG_W_RUN_PROPERTIES:
                run_properties = child
            else:
                self._handle_run_child(
                    child,
                    part,
                    block_id,
                    raw_hints,
                    parsed_run,
                    text_parts,
                )

        # 在遍历完子节点后，解析 rPr（前面已在循环中找到）。
        if run_properties is not None:
            rstyle = first_child(run_properties, "w", "rStyle")
            run_style_id = attr(rstyle, "w", "val") if rstyle is not None else None
            if run_style_id is not None:
                parsed_run["styleId"] = run_style_id
            run_format = merge_run_formats(
                self.styles.resolve_run_format(paragraph_style_id),
                self.styles.resolve_run_format(run_style_id),
                parse_run_format(run_properties),
            )
            visible_format = visible_run_format(run_format)
            if visible_format:
                parsed_run["format"] = visible_format

        parsed_run["text"] = "".join(text_parts)
        return parsed_run

    def _handle_run_child(
        self,
        child: ET.Element,
        part: str,
        block_id: str,
        raw_hints: list[RawHint],
        parsed_run: Run,
        text_parts: list[str],
    ) -> None:
        """Dispatch one run child into text, inline objects or warnings."""
        child_tag = child.tag
        if child_tag == _TAG_W_TEXT:
            if attr(child, "xml", "space") == "preserve":
                parsed_run["preserveSpace"] = True
            text_parts.append(child.text or "")
        elif child_tag == _TAG_W_TAB:
            text_parts.append("\t")
        elif child_tag in (_TAG_W_BREAK, _TAG_W_CARRIAGE_RETURN):
            text_parts.append("\n")
            if attr(child, "w", "type") == "page":
                raw_hints.append({"type": "manualPageBreak"})
                self._mark_page_break()
        elif child_tag == _TAG_W_LAST_RENDERED_PAGE_BREAK:
            raw_hints.append({"type": "lastRenderedPageBreak"})
            self._mark_page_break()
        elif child_tag == _TAG_W_DRAWING:
            objects = self._drawing_objects(child, part)
            parsed_run.setdefault("objects", []).extend(objects)
            raw_hints.extend({"type": "drawing", **obj} for obj in objects)
        elif child_tag == _TAG_W_PICTURE:
            objects = self._pict_objects(child)
            parsed_run.setdefault("objects", []).extend(objects)
            raw_hints.extend({"type": "pict", **obj} for obj in objects)
        elif child_tag in (_TAG_M_OMATH, _TAG_M_OMATH_PARA):
            obj = self._equation_object(child)
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag in (_TAG_W_FLD_CHAR, _TAG_W_INSTR_TEXT):
            lname = local_name(child_tag)
            field_hint: RawHint = {"type": "field", "node": lname}
            if lname == "instrText" and child.text:
                field_hint["instruction"] = child.text
                parsed_run.setdefault("objects", []).append(
                    {"type": "fieldInstruction", "instruction": child.text}
                )
            raw_hints.append(field_hint)
        elif child_tag in (_TAG_W_FOOTNOTE_REF, _TAG_W_ENDNOTE_REF, _TAG_W_ANNOTATION_REF):
            return
        elif child_tag in (_TAG_W_FOOTNOTE_REFERENCE, _TAG_W_ENDNOTE_REFERENCE):
            note_id = attr(child, "w", "id")
            lname = local_name(child_tag)
            ref_type = "footnote" if lname == "footnoteReference" else "endnote"
            obj = {"type": f"{ref_type}Ref", "id": note_id}
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_COMMENT_REFERENCE:
            obj = {"type": "commentRef", "id": attr(child, "w", "id")}
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_DELETION_TEXT:
            # final 视图默认不读删除文本。
            self._warn(
                "DELETED_TEXT_SKIPPED",
                "Encountered deleted text in run; parser skips deleted text in final mode.",
                part=part,
                block_id=block_id,
            )
        elif child_tag == _TAG_W_OBJECT:
            obj = self._parse_embedded_object(child)
            parsed_run.setdefault("objects", []).append(obj)
            raw_hints.append(obj)
        elif child_tag == _TAG_W_RUN_STYLE:
            # rStyle 由下方 rPr 段落统一用 first_child 提取，此处仅跳过。
            return
        else:
            self._warn(
                "UNSUPPORTED_RUN_CHILD",
                f"Encountered unsupported run child: {local_name(child_tag)}",
                part=part,
                block_id=block_id,
            )

    def _hyperlink_info(self, node: ET.Element, part: str) -> LinkInfo:
        """解析超链接目标，最终 XML 只使用 href/anchor。"""
        rel_id = attr(node, "r", "id")
        anchor = attr(node, "w", "anchor")
        info: LinkInfo = {}
        if rel_id:
            rel = self.relationships.require(part, rel_id)
            info["href"] = rel.resolved_target or rel.target
        if anchor:
            info["anchor"] = anchor
        return info

    def _drawing_objects(self, drawing: ET.Element, part: str) -> list[InlineObject]:
        """从 DrawingML 中提取图片引用、文本框和轻量图形占位。"""
        placement, container = self._drawing_container(drawing)
        common = self._drawing_common_attrs(container, placement)
        objects: list[InlineObject] = []

        for chart in drawing.iter(qualified_name("c", "chart")):
            # chart 引用指向 word/charts/chart*.xml，正文只挂轻量摘要对象。
            rel_id = attr(chart, "r", "id")
            if rel_id:
                objects.append(self._referenced_object(part, rel_id, "chart", common))

        for rel_ids in drawing.iter(qualified_name("dgm", "relIds")):
            # SmartArt 的数据模型在 r:dm 指向的 diagram data part 中。
            rel_id = attr(rel_ids, "r", "dm")
            if rel_id:
                objects.append(self._referenced_object(part, rel_id, "smartart", common))

        blip = drawing.find(".//" + qualified_name("a", "blip"))
        rel_id = attr(blip, "r", "embed") if blip is not None else None
        if rel_id:
            asset = self.asset_lookup.get((part, rel_id))
            if asset is not None:
                image: InlineObject = {"type": "image"}
                self._copy_drawing_common(image, common)
                image["assetId"] = asset["id"]
                if "file" in asset:
                    image["file"] = asset["file"]
                if "href" in asset:
                    image["href"] = asset["href"]
                objects.append(image)
            else:
                # 资源缺失时保留图形占位，避免最终 XML 误指向不存在的图片。
                drawing_obj: InlineObject = {"type": "drawing"}
                self._copy_drawing_common(drawing_obj, common)
                objects.append(drawing_obj)

        for txbx in self._textbox_content_nodes(drawing):
            # 文本框文字可能是用户直接可见正文，必须进入最终 XML。
            text = self._container_plain_text(txbx)
            if text.strip():
                textbox: InlineObject = {"type": "textbox", "text": text}
                self._copy_drawing_common(textbox, common)
                objects.append(textbox)

        if objects:
            return objects
        fallback_obj: InlineObject = {"type": "drawing"}
        self._copy_drawing_common(fallback_obj, common)
        return [fallback_obj]

    def _referenced_object(
        self, part: str, rel_id: str, fallback_type: str, common: DrawingCommon
    ) -> InlineObject:
        """读取预解析对象；缺失时降级为轻量占位。"""
        parsed = self.object_lookup.get((part, rel_id))
        if parsed is None:
            obj: InlineObject = {"type": fallback_type, "id": rel_id}
            self._copy_drawing_common(obj, common)
            return obj
        obj = self._object_from_lookup(parsed)
        self._copy_drawing_common(obj, common)
        return obj

    def _pict_objects(self, pict: ET.Element) -> list[InlineObject]:
        """从旧式 VML pict 中提取文本框；其它图形保留占位。"""
        objects: list[InlineObject] = []
        common: DrawingCommon = {"placement": "vml"}
        for shape in pict.iter(qualified_name("v", "shape")):
            shape_id = shape.get("id")
            alt = shape.get("alt")
            if shape_id:
                common["name"] = shape_id
            if alt:
                common["alt"] = alt

        for txbx in self._textbox_content_nodes(pict):
            text = self._container_plain_text(txbx)
            if text.strip():
                textbox: InlineObject = {"type": "textbox", "text": text}
                self._copy_drawing_common(textbox, common)
                objects.append(textbox)
        if objects:
            return objects
        drawing: InlineObject = {"type": "drawing"}
        self._copy_drawing_common(drawing, common)
        return [drawing]

    def _parse_embedded_object(self, obj_elem: ET.Element) -> InlineObject:
        """从 w:object 元素中提取嵌入对象类型。"""
        result: InlineObject = {"type": "embedded"}
        ole = first_child(obj_elem, "o", "OLEObject")
        if ole is not None:
            progid = ole.get("ProgID", "")
            if progid:
                result["embeddedType"] = _progid_to_type(progid)
                result["progid"] = progid
        if "embeddedType" not in result:
            result["embeddedType"] = "unknown"
        # 尝试从 shape/docPr 提取名称
        for shape in obj_elem.iter(qualified_name("v", "shape")):
            title = shape.get("title") or shape.get("alt")
            if title:
                result["name"] = title
                break
        if "name" not in result:
            for doc_pr in obj_elem.iter(qualified_name("wp", "docPr")):
                name = doc_pr.get("name")
                if name:
                    result["name"] = name
                    break
        return result

    def _copy_drawing_common(self, obj: InlineObject, common: DrawingCommon) -> None:
        """Copy shared DrawingML/VML metadata without TypedDict ** expansion."""
        if "placement" in common:
            obj["placement"] = common["placement"]
        if "name" in common:
            obj["name"] = common["name"]
        if "alt" in common:
            obj["alt"] = common["alt"]
        if "title" in common:
            obj["title"] = common["title"]
        if "cx" in common:
            obj["cx"] = common["cx"]
        if "cy" in common:
            obj["cy"] = common["cy"]

    def _object_from_lookup(self, parsed: Chart | SmartArt) -> InlineObject:
        """Convert a parsed chart/SmartArt object to the inline-object shape."""
        obj: InlineObject = {
            "type": parsed["type"],
            "id": parsed["id"],
            "part": parsed["part"],
        }
        if parsed["type"] == "chart":
            obj["chartType"] = parsed["chartType"]
            obj["seriesCount"] = parsed["seriesCount"]
            obj["pointCount"] = parsed["pointCount"]
            obj["series"] = parsed["series"]
            if "title" in parsed:
                obj["title"] = parsed["title"]
        else:
            obj["nodeCount"] = parsed["nodeCount"]
            obj["linkCount"] = parsed["linkCount"]
            obj["rawLinkCount"] = parsed["rawLinkCount"]
            obj["nodes"] = parsed["nodes"]
            obj["links"] = parsed["links"]
            if "layoutType" in parsed:
                obj["layoutType"] = parsed["layoutType"]
        if "sourcePart" in parsed:
            obj["sourcePart"] = parsed["sourcePart"]
        if "relationshipId" in parsed:
            obj["relationshipId"] = parsed["relationshipId"]
        return obj

    def _drawing_container(self, drawing: ET.Element) -> tuple[str, ET.Element | None]:
        """识别 DrawingML 是 inline 还是 anchor。"""
        inline = drawing.find(".//" + qualified_name("wp", "inline"))
        anchor = drawing.find(".//" + qualified_name("wp", "anchor"))
        if inline is not None:
            return ("inline", inline)
        if anchor is not None:
            return ("anchor", anchor)
        return ("drawing", None)

    def _drawing_common_attrs(self, container: ET.Element | None, placement: str) -> DrawingCommon:
        """提取图片、形状、文本框共用的轻量辅助信息。"""
        obj: DrawingCommon = {"placement": placement}
        if container is None:
            return obj
        doc_pr = container.find(".//" + qualified_name("wp", "docPr"))
        if doc_pr is not None:
            name = doc_pr.get("name")
            descr = doc_pr.get("descr")
            title = doc_pr.get("title")
            if name:
                obj["name"] = name
            if descr:
                obj["alt"] = descr
            if title:
                obj["title"] = title
        extent = first_child(container, "wp", "extent")
        if extent is not None:
            obj["cx"] = extent.attrib["cx"]
            obj["cy"] = extent.attrib["cy"]
        return obj

    def _textbox_content_nodes(self, node: ET.Element) -> list[ET.Element]:
        """查找 DrawingML/WPS/VML 文本框中的 w:txbxContent。"""
        return list(node.iter(qualified_name("w", "txbxContent")))

    def _equation_object(self, node: ET.Element) -> InlineObject:
        """把 OMML 公式转换为 LaTeX 字符串。LLM 对 LaTeX 数学表达理解极好。"""
        text = omath_to_latex(node)
        return {"type": "equation", "text": text}

    def _container_plain_text(self, node: ET.Element) -> str:
        """提取文本框内的轻量纯文本，并保留段落/表格分隔。"""
        parts: list[str] = []
        for child in node:
            lname = local_name(child.tag)
            if lname == "p":
                text = self._inline_plain_text(child)
                if text.strip():
                    parts.append(text)
            elif lname == "tbl":
                text = self._table_plain_text(child)
                if text.strip():
                    parts.append(text)
            else:
                text = self._inline_plain_text(child)
                if text.strip():
                    parts.append(text)
        return "\n".join(parts)

    def _table_plain_text(self, tbl: ET.Element) -> str:
        """把文本框内表格压缩为行文本。"""
        rows: list[str] = []
        for tr in child_elements(tbl, "w", "tr"):
            cells = [self._container_plain_text(tc) for tc in child_elements(tr, "w", "tc")]
            row = " | ".join(cell.strip() for cell in cells if cell.strip())
            if row:
                rows.append(row)
        return "\n".join(rows)

    def _inline_plain_text(self, node: ET.Element) -> str:
        """提取一个节点子树内显式文本。"""
        parts: list[str] = []
        for item in node.iter():
            lname = local_name(item.tag)
            if lname == "t":
                parts.append(item.text or "")
            elif lname == "tab":
                parts.append("\t")
            elif lname in {"br", "cr"}:
                parts.append("\n")
        return "".join(parts)

    def _mark_page_break(self) -> None:
        """通知正文解析器当前 block 后需要推进 page hint。"""
        if self.on_page_break is not None:
            self.on_page_break()

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
                code=code,
                message=message,
                locator=":".join(filter(None, [part, block_id])),
            )
        )
