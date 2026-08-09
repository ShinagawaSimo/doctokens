"""OOXML namespaces and XML utilities - DOCX specific.

Shared XML helper logic is implemented by delegating to ``ooxml_llm_core.xml``,
providing a wrapper on top of the DOCX ``NS`` only.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

# Shared helper implementations (aliased to avoid conflicts with local wrappers)
# isort: split
from ooxml_llm_core.xml import NS as _NS_OPC
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
    local_name,
)
from ooxml_llm_core.xml import (
    qualified_name as _core_qualified_name,
)

# -- Complete DOCX namespace mapping --

NS = {
    **_NS_OPC,
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
}

# -- Delegation wrappers --


def qualified_name(prefix: str, local: str) -> str:
    return _core_qualified_name(prefix, local, NS)


def attr(el: ET.Element, prefix: str, local: str, default: str | None = None) -> str | None:
    return _core_attr(el, prefix, local, default, NS)


def first_child(el: ET.Element | None, prefix: str, local: str) -> ET.Element | None:
    return _core_first_child(el, prefix, local, NS)


def child_elements(el: ET.Element | None, prefix: str, local: str) -> list[ET.Element]:
    return _core_child_elements(el, prefix, local, NS)


# -- Word-specific helpers --


def is_on(el: ET.Element | None) -> bool:
    """Check whether a Word boolean attribute is enabled."""
    if el is None:
        return False
    val = attr(el, "w", "val")
    if val is None:
        return True
    return val.lower() not in {"0", "false", "off", "none"}


# -- Precomputed hot-path tag names --
# Avoid repeated f"{{{ns}}}{local}" string concatenation on every qualified_name(prefix, local) call.
# These tag names are used heavily in find/findall/iter operations during body/inline parsing.
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

# Precomputed tags for drawing/chart/diagram namespaces
_TAG_A_BLIP = qualified_name("a", "blip")
_TAG_C_CHART = qualified_name("c", "chart")
_TAG_DGM_REL_IDS = qualified_name("dgm", "relIds")

__all__ = [
    "NS",
    "_TAG_A_BLIP",
    "_TAG_C_CHART",
    "_TAG_DGM_REL_IDS",
    "_TAG_M_OMATH",
    "_TAG_M_OMATH_PARA",
    "_TAG_W_ANNOTATION_REF",
    "_TAG_W_BASED_ON",
    "_TAG_W_BODY",
    "_TAG_W_BOOKMARK_END",
    "_TAG_W_BOOKMARK_START",
    "_TAG_W_BREAK",
    "_TAG_W_CARRIAGE_RETURN",
    "_TAG_W_CELL_PROPERTIES",
    "_TAG_W_COMMENT_RANGE_END",
    "_TAG_W_COMMENT_RANGE_START",
    "_TAG_W_COMMENT_REFERENCE",
    "_TAG_W_DELETION",
    "_TAG_W_DELETION_TEXT",
    "_TAG_W_DRAWING",
    "_TAG_W_ENDNOTE_REF",
    "_TAG_W_ENDNOTE_REFERENCE",
    "_TAG_W_FLD_CHAR",
    "_TAG_W_FOOTNOTE_REF",
    "_TAG_W_FOOTNOTE_REFERENCE",
    "_TAG_W_GRID_SPAN",
    "_TAG_W_HYPERLINK",
    "_TAG_W_INDENT_LEVEL",
    "_TAG_W_INSERTION",
    "_TAG_W_INSTR_TEXT",
    "_TAG_W_LAST_RENDERED_PAGE_BREAK",
    "_TAG_W_NAME",
    "_TAG_W_NEXT",
    "_TAG_W_NUMBERING_ID",
    "_TAG_W_NUMBERING_PROPERTIES",
    "_TAG_W_OBJECT",
    "_TAG_W_OUTLINE_LEVEL",
    "_TAG_W_PARAGRAPH",
    "_TAG_W_PARAGRAPH_PROPERTIES",
    "_TAG_W_PARAGRAPH_STYLE",
    "_TAG_W_PERMISSION_END",
    "_TAG_W_PERMISSION_START",
    "_TAG_W_PICTURE",
    "_TAG_W_PROOF_ERROR",
    "_TAG_W_RUN",
    "_TAG_W_RUN_PROPERTIES",
    "_TAG_W_RUN_STYLE",
    "_TAG_W_SDT_CONTENT",
    "_TAG_W_SECTION_PROPERTIES",
    "_TAG_W_SMART_TAG",
    "_TAG_W_STRUCTURED_DOCUMENT_TAG",
    "_TAG_W_STYLE",
    "_TAG_W_TAB",
    "_TAG_W_TABLE",
    "_TAG_W_TABLE_CELL",
    "_TAG_W_TABLE_HEADER",
    "_TAG_W_TABLE_ROW",
    "_TAG_W_TEXT",
    "_TAG_W_VERTICAL_MERGE",
    "attr",
    "child_elements",
    "first_child",
    "is_on",
    "local_name",
    "qualified_name",
]
