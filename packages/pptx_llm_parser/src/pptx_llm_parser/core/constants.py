"""OOXML namespace map + XML helper functions + precomputed hot-path tag names."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ooxml_llm_core.xml import (
    attr as _core_attr,
)
from ooxml_llm_core.xml import (
    child_elements as _core_child_elements,
)
from ooxml_llm_core.xml import (
    first_child as _core_first_child,
)
from ooxml_llm_core.xml import (
    local_name as _core_local_name,
)
from ooxml_llm_core.xml import (
    qualified_name as _core_qualified_name,
)

# OPC-level prefixes shared with ooxml_llm_core.
_NS_OPC = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

NS = {
    **_NS_OPC,
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p15": "http://schemas.microsoft.com/office/powerpoint/2012/main",
    "p16": "http://schemas.microsoft.com/office/powerpoint/2015/09/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def qualified_name(prefix: str, local: str) -> str:
    return _core_qualified_name(prefix, local, ns=NS)


def local_name(tag: str) -> str:
    return _core_local_name(tag)


def attr(element: ET.Element, prefix: str, local: str, default: str | None = None) -> str | None:
    return _core_attr(element, prefix, local, default=default, ns=NS)


def first_child(element: ET.Element, prefix: str, local: str) -> ET.Element | None:
    return _core_first_child(element, prefix, local, ns=NS)


def child_elements(element: ET.Element, prefix: str, local: str) -> list[ET.Element]:
    return _core_child_elements(element, prefix, local, ns=NS)


# Precomputed hot-path tag names (avoid repeated string concatenation).
_TAG_P_SLD = qualified_name("p", "sld")
_TAG_P_CSLD = qualified_name("p", "cSld")
_TAG_P_SPTREE = qualified_name("p", "spTree")
_TAG_P_SP = qualified_name("p", "sp")
_TAG_P_TXBODY = qualified_name("p", "txBody")
_TAG_P_SLDIDLST = qualified_name("p", "sldIdLst")
_TAG_P_SLDID = qualified_name("p", "sldId")
_TAG_P_SLDSZ = qualified_name("p", "sldSz")
_TAG_A_P = qualified_name("a", "p")
_TAG_A_R = qualified_name("a", "r")
_TAG_A_T = qualified_name("a", "t")
_TAG_A_BR = qualified_name("a", "br")
_TAG_A_TAB = qualified_name("a", "tab")

__all__ = [
    "NS",
    "_TAG_A_BR",
    "_TAG_A_P",
    "_TAG_A_R",
    "_TAG_A_T",
    "_TAG_A_TAB",
    "_TAG_P_CSLD",
    "_TAG_P_SLD",
    "_TAG_P_SLDID",
    "_TAG_P_SLDIDLST",
    "_TAG_P_SLDSZ",
    "_TAG_P_SP",
    "_TAG_P_SPTREE",
    "_TAG_P_TXBODY",
    "attr",
    "child_elements",
    "first_child",
    "local_name",
    "qualified_name",
]
