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
