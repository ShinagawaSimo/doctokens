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
    "v": "urn:schemas-microsoft-com:vml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def qn(prefix: str, local: str) -> str:
    """生成 ElementTree 使用的 Clark notation 标签名。"""
    return f"{{{NS[prefix]}}}{local}"


def local_name(tag: str) -> str:
    """从带命名空间的标签名中取 local name。"""
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[1]
    return tag


def local_name_fast(tag: str) -> str:
    """local_name 的快速版本：用 rfind 避免 split 的内存分配。
    热路径（body/inline 解析）中标签名比较频繁，此版本可减少 GC 压力。"""
    brace = tag.rfind("}")
    if brace != -1:
        return tag[brace + 1 :]
    return tag


# ── 预计算热路径标签名 ──
# 避免每次调用 qn(prefix, local) 时重复做 f"{{{ns}}}{local}" 字符串拼接。
# body/inline 解析中这些标签名被频繁用于 find/findall/iter 等操作。
_TAG_W_BODY = qn("w", "body")
_TAG_W_P = qn("w", "p")
_TAG_W_R = qn("w", "r")
_TAG_W_RPR = qn("w", "rPr")
_TAG_W_PPR = qn("w", "pPr")
_TAG_W_T = qn("w", "t")
_TAG_W_TBL = qn("w", "tbl")
_TAG_W_TR = qn("w", "tr")
_TAG_W_TC = qn("w", "tc")
_TAG_W_TC_PR = qn("w", "tcPr")
_TAG_W_BR = qn("w", "br")
_TAG_W_CR = qn("w", "cr")
_TAG_W_TAB = qn("w", "tab")
_TAG_W_DRAWING = qn("w", "drawing")
_TAG_W_PICT = qn("w", "pict")
_TAG_W_HYPERLINK = qn("w", "hyperlink")
_TAG_W_INS = qn("w", "ins")
_TAG_W_DEL = qn("w", "del")
_TAG_W_DEL_TEXT = qn("w", "delText")
_TAG_W_SDT = qn("w", "sdt")
_TAG_W_SDT_CONTENT = qn("w", "sdtContent")
_TAG_W_SMART_TAG = qn("w", "smartTag")
_TAG_W_BOOKMARK_START = qn("w", "bookmarkStart")
_TAG_W_BOOKMARK_END = qn("w", "bookmarkEnd")
_TAG_W_PROOF_ERR = qn("w", "proofErr")
_TAG_W_PERM_START = qn("w", "permStart")
_TAG_W_PERM_END = qn("w", "permEnd")
_TAG_W_COMMENT_RANGE_START = qn("w", "commentRangeStart")
_TAG_W_COMMENT_RANGE_END = qn("w", "commentRangeEnd")
_TAG_W_FOOTNOTE_REF = qn("w", "footnoteRef")
_TAG_W_ENDNOTE_REF = qn("w", "endnoteRef")
_TAG_W_ANNOTATION_REF = qn("w", "annotationRef")
_TAG_W_FOOTNOTE_REFERENCE = qn("w", "footnoteReference")
_TAG_W_ENDNOTE_REFERENCE = qn("w", "endnoteReference")
_TAG_W_COMMENT_REFERENCE = qn("w", "commentReference")
_TAG_W_FLD_CHAR = qn("w", "fldChar")
_TAG_W_INSTR_TEXT = qn("w", "instrText")
_TAG_W_LAST_RENDERED_PAGE_BREAK = qn("w", "lastRenderedPageBreak")
_TAG_W_SECT_PR = qn("w", "sectPr")
_TAG_W_P_STYLE = qn("w", "pStyle")
_TAG_W_R_STYLE = qn("w", "rStyle")
_TAG_W_NUM_PR = qn("w", "numPr")
_TAG_W_NUM_ID = qn("w", "numId")
_TAG_W_ILVL = qn("w", "ilvl")
_TAG_W_GRID_SPAN = qn("w", "gridSpan")
_TAG_W_V_MERGE = qn("w", "vMerge")
_TAG_W_TBL_HEADER = qn("w", "tblHeader")
_TAG_W_OUTLINE_LVL = qn("w", "outlineLvl")
_TAG_W_BASED_ON = qn("w", "basedOn")
_TAG_W_NEXT = qn("w", "next")
_TAG_W_NAME = qn("w", "name")
_TAG_W_STYLE = qn("w", "style")
_TAG_M_OMATH = qn("m", "oMath")
_TAG_M_OMATH_PARA = qn("m", "oMathPara")

# 绘图/图表/图示命名空间预计算标签
_TAG_A_BLIP = qn("a", "blip")
_TAG_C_CHART = qn("c", "chart")
_TAG_DGM_REL_IDS = qn("dgm", "relIds")


def attr(el: ET.Element, prefix: str, local: str, default: str | None = None) -> str | None:
    """读取带命名空间的 XML 属性。"""
    return el.get(qn(prefix, local), default)


def first_child(el: ET.Element | None, prefix: str, local: str) -> ET.Element | None:
    """查找第一个指定名称的直接子元素。"""
    if el is None:
        return None
    wanted = qn(prefix, local)
    for child in el:
        # 只看直接子节点，避免误读深层嵌套结构。
        if child.tag == wanted:
            return child
    return None


def child_elements(el: ET.Element | None, prefix: str, local: str) -> list[ET.Element]:
    """查找指定名称的所有直接子元素。"""
    if el is None:
        return []
    wanted = qn(prefix, local)
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
