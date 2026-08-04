"""OOXML 命名空间和 XML 小工具。"""

from __future__ import annotations

from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "o": "urn:schemas-microsoft-com:office:office",
    "v": "urn:schemas-microsoft-com:vml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def qualified_name(prefix: str, local: str) -> str:
    """生成 ElementTree 使用的 Clark notation 标签名。"""
    return f"{{{NS[prefix]}}}{local}"


def local_name(tag: str) -> str:
    """从带命名空间的标签名中取 local name。使用 rfind 避免 split 的内存分配。"""
    brace = tag.rfind("}")
    if brace != -1:
        return tag[brace + 1 :]
    return tag


# ── 预计算热路径标签名 ──
# 避免每次调用 qualified_name(prefix, local) 时重复做 f"{{{ns}}}{local}" 字符串拼接。
# body/inline 解析中这些标签名被频繁用于 find/findall/iter 等操作。
_TAG_W_BODY = qualified_name("w", "body")
_TAG_W_PARAGRAPH = qualified_name("w", "p")
_TAG_W_RUN = qualified_name("w", "r")
_TAG_W_RUN_PROPERTIES = qualified_name("w", "rPr")
_TAG_W_PARAGRAPH_PROPERTIES = qualified_name("w", "pPr")
_TAG_W_TEXT = qualified_name("w", "t")
_TAG_W_TABLE = qualified_name("w", "tbl")
_TAG_W_TABLE_ROW = qualified_name("w", "tr")
_TAG_W_TABLE_CELL = qualified_name("w", "tc")
_TAG_W_CELL_PROPERTIES = qualified_name("w", "tcPr")
_TAG_W_BREAK = qualified_name("w", "br")
_TAG_W_CARRIAGE_RETURN = qualified_name("w", "cr")
_TAG_W_TAB = qualified_name("w", "tab")
_TAG_W_OBJECT = qualified_name("w", "object")
_TAG_W_DRAWING = qualified_name("w", "drawing")
_TAG_W_PICTURE = qualified_name("w", "pict")
_TAG_W_HYPERLINK = qualified_name("w", "hyperlink")
_TAG_W_INSERTION = qualified_name("w", "ins")
_TAG_W_DELETION = qualified_name("w", "del")
_TAG_W_DELETION_TEXT = qualified_name("w", "delText")
_TAG_W_STRUCTURED_DOCUMENT_TAG = qualified_name("w", "sdt")
_TAG_W_SDT_CONTENT = qualified_name("w", "sdtContent")
_TAG_W_SMART_TAG = qualified_name("w", "smartTag")
_TAG_W_BOOKMARK_START = qualified_name("w", "bookmarkStart")
_TAG_W_BOOKMARK_END = qualified_name("w", "bookmarkEnd")
_TAG_W_PROOF_ERROR = qualified_name("w", "proofErr")
_TAG_W_PERMISSION_START = qualified_name("w", "permStart")
_TAG_W_PERMISSION_END = qualified_name("w", "permEnd")
_TAG_W_COMMENT_RANGE_START = qualified_name("w", "commentRangeStart")
_TAG_W_COMMENT_RANGE_END = qualified_name("w", "commentRangeEnd")
_TAG_W_FOOTNOTE_REF = qualified_name("w", "footnoteRef")
_TAG_W_ENDNOTE_REF = qualified_name("w", "endnoteRef")
_TAG_W_ANNOTATION_REF = qualified_name("w", "annotationRef")
_TAG_W_FOOTNOTE_REFERENCE = qualified_name("w", "footnoteReference")
_TAG_W_ENDNOTE_REFERENCE = qualified_name("w", "endnoteReference")
_TAG_W_COMMENT_REFERENCE = qualified_name("w", "commentReference")
_TAG_W_FLD_CHAR = qualified_name("w", "fldChar")
_TAG_W_INSTR_TEXT = qualified_name("w", "instrText")
_TAG_W_LAST_RENDERED_PAGE_BREAK = qualified_name("w", "lastRenderedPageBreak")
_TAG_W_SECTION_PROPERTIES = qualified_name("w", "sectPr")
_TAG_W_PARAGRAPH_STYLE = qualified_name("w", "pStyle")
_TAG_W_RUN_STYLE = qualified_name("w", "rStyle")
_TAG_W_NUMBERING_PROPERTIES = qualified_name("w", "numPr")
_TAG_W_NUMBERING_ID = qualified_name("w", "numId")
_TAG_W_INDENT_LEVEL = qualified_name("w", "ilvl")
_TAG_W_GRID_SPAN = qualified_name("w", "gridSpan")
_TAG_W_VERTICAL_MERGE = qualified_name("w", "vMerge")
_TAG_W_TABLE_HEADER = qualified_name("w", "tblHeader")
_TAG_W_OUTLINE_LEVEL = qualified_name("w", "outlineLvl")
_TAG_W_BASED_ON = qualified_name("w", "basedOn")
_TAG_W_NEXT = qualified_name("w", "next")
_TAG_W_NAME = qualified_name("w", "name")
_TAG_W_STYLE = qualified_name("w", "style")
_TAG_M_OMATH = qualified_name("m", "oMath")
_TAG_M_OMATH_PARA = qualified_name("m", "oMathPara")

# 绘图/图表/图示命名空间预计算标签
_TAG_A_BLIP = qualified_name("a", "blip")
_TAG_C_CHART = qualified_name("c", "chart")
_TAG_DGM_REL_IDS = qualified_name("dgm", "relIds")


def attr(el: ET.Element, prefix: str, local: str, default: str | None = None) -> str | None:
    """读取带命名空间的 XML 属性。"""
    return el.get(qualified_name(prefix, local), default)


def first_child(el: ET.Element | None, prefix: str, local: str) -> ET.Element | None:
    """查找第一个指定名称的直接子元素。"""
    if el is None:
        return None
    wanted = qualified_name(prefix, local)
    for child in el:
        # 只看直接子节点，避免误读深层嵌套结构。
        if child.tag == wanted:
            return child
    return None


def child_elements(el: ET.Element | None, prefix: str, local: str) -> list[ET.Element]:
    """查找指定名称的所有直接子元素。"""
    if el is None:
        return []
    wanted = qualified_name(prefix, local)
    return [child for child in el if child.tag == wanted]


def is_on(el: ET.Element | None) -> bool:
    """判断 Word 布尔属性是否开启。"""
    if el is None:
        return False
    val = attr(el, "w", "val")
    if val is None:
        # Word 中 <w:b/> 这类空元素通常表示开启。
        return True
    return val.lower() not in {"0", "false", "off", "none"}
