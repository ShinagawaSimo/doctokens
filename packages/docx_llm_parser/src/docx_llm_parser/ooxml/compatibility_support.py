"""Conservative reading capabilities used to preflight DOCX compatibility choices."""

from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree as ET

from ..core.constants import NS, attr, qualified_name
from ..core.models import AssetLookup

# A namespace being declared in the document is not evidence of parser support.
# Geometry-only extensions and Word groups are deliberately not advertised here.
SUPPORTED_NAMESPACES = frozenset(NS[p] for p in ("w", "wp", "a", "c", "dgm", "m", "v", "wps")) | {
    "http://schemas.openxmlformats.org/drawingml/2006/picture",
}


def _tags(prefix: str, names: str) -> set[str]:
    return {qualified_name(prefix, name) for name in names.split()}


_MATH = _tags("m", "oMath oMathPara")
_MARKERS = _tags("w", "bookmarkStart bookmarkEnd proofErr permStart permEnd commentRangeStart commentRangeEnd")
_INLINE_WRAPPERS = _tags("w", "hyperlink ins moveTo del moveFrom sdtContent smartTag fldSimple")
_DRAWING_CONTAINERS = (
    _tags("wp", "inline anchor")
    | _tags("a", "graphic graphicData")
    | _tags("wps", "wsp txbx")
    | _tags("v", "group shape rect roundrect oval line polyline arc curve image textbox")
    | {"{http://schemas.openxmlformats.org/drawingml/2006/picture}pic"}
)
_ALLOWED = {
    "block": _tags("w", "p tbl sdt sectPr tcPr") | _MARKERS,
    "inline": _tags("w", "pPr r sdt object") | _INLINE_WRAPPERS | _MARKERS | _MATH,
    "run": _tags(
        "w",
        "rPr t tab br cr lastRenderedPageBreak drawing pict fldChar instrText footnoteRef endnoteRef "
        "annotationRef footnoteReference endnoteReference commentReference delText object rStyle",
    )
    | _MATH,
    "table": _tags("w", "tblPr tblGrid tr"),
    "row": _tags("w", "trPr tc"),
    "cell": _tags("w", "tcPr p tbl"),
    "drawing": _DRAWING_CONTAINERS
    | _tags("w", "txbxContent")
    | _tags("a", "blip")
    | _tags("v", "imagedata")
    | _tags("c", "chart")
    | _tags("dgm", "relIds"),
}
_CONTEXTS = {
    **{qualified_name("w", n): "block" for n in ("body", "txbxContent", "hdr", "ftr", "footnote", "endnote", "comment")},
    qualified_name("w", "p"): "inline",
    qualified_name("w", "r"): "run",
    qualified_name("w", "tbl"): "table",
    qualified_name("w", "tr"): "row",
    qualified_name("w", "tc"): "cell",
    qualified_name("w", "drawing"): "drawing",
    qualified_name("w", "pict"): "drawing",
    **dict.fromkeys(_DRAWING_CONTAINERS, "drawing"),
}
_SDT = qualified_name("w", "sdt")
_SDT_CONTENT = qualified_name("w", "sdtContent")
_DRAWING = qualified_name("w", "drawing")
_PICT = qualified_name("w", "pict")
_TEXTBOX = qualified_name("w", "txbxContent")
_OBJECT = qualified_name("w", "object")


def child_context(tag: str, inherited: str) -> str:
    """Identify the content dispatcher that will receive expanded children."""
    if tag in _INLINE_WRAPPERS or tag in {_SDT, _SDT_CONTENT}:
        return inherited
    return _CONTEXTS.get(tag, "other")


def can_process(nodes: Iterable[ET.Element], context: str, part: str, assets: AssetLookup) -> bool:
    """Check capability without applying fields, anchors, pagination or diagnostics.

    Empty branches succeed. A generic drawing/OLE placeholder does not demonstrate
    that the content of a Choice can be read. Formatting inside recognized nodes
    continues to use the ordinary parser's density and unsupported-format rules.
    """
    return all(_can_process_node(node, context, part, assets) for node in nodes)


def _can_process_node(node: ET.Element, context: str, part: str, assets: AssetLookup) -> bool:
    if node.tag not in _ALLOWED.get(context, set()):
        return False
    if node.tag in {_DRAWING, _PICT} or context == "drawing":
        return _can_process_drawing(node, part, assets)
    if node.tag == _OBJECT:
        return False
    if node.tag == _SDT:
        content = node.find(_SDT_CONTENT)
        return content is None or can_process(content, context, part, assets)
    if node.tag in _CONTEXTS or node.tag in _INLINE_WRAPPERS:
        return can_process(node, child_context(node.tag, context), part, assets)
    return True


def _can_process_drawing(node: ET.Element, part: str, assets: AssetLookup) -> bool:
    textboxes = list(node.iter(_TEXTBOX))
    if textboxes:
        # A deliberately empty text box is valid; do not resurrect fallback text.
        return all(can_process(box, "block", part, assets) for box in textboxes)
    for item in node.iter():
        if item.tag in {qualified_name("a", "blip"), qualified_name("v", "imagedata")}:
            reference = "embed" if item.tag == qualified_name("a", "blip") else "id"
            if (part, attr(item, "r", reference) or "") in assets:
                return True
        elif (item.tag == qualified_name("c", "chart") and attr(item, "r", "id")) or (
            item.tag == qualified_name("dgm", "relIds") and attr(item, "r", "dm")
        ):
            return True
    return False
