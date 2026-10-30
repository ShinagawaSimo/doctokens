"""Read only explicit comment target identities, without retaining source trees."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..model.presentation import CommentTarget, ShapeBlock

MODERN_NS = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"
_PC = "{http://schemas.microsoft.com/office/powerpoint/2013/main/command}"
_OAC = "{http://schemas.microsoft.com/office/drawing/2013/main/command}"
_ANCHORS = (
    {_PC + name for name in ("sldMkLst", "sldLayoutMkLst", "sldMasterMkLst")}
    | {_OAC + name for name in ("deMkLst", "txBodyMkLst", "txMkLst", "tcMkLst", "trMkLst", "gridColMkLst")}
    | {"{" + MODERN_NS + "}unknownAnchor"}
)
_SHAPES = {_OAC + name for name in ("spMk", "picMk", "cxnSpMk", "graphicFrameMk", "inkMk", "grpSpMk")}


def read_target(comment: ET.Element) -> tuple[str | None, CommentTarget | None]:
    slide_id = None
    target: CommentTarget | None = None
    for anchor in comment:
        if anchor.tag not in _ANCHORS:
            continue
        if target is None:
            target = {}
        template_target = any(
            node.tag in {_PC + name for name in ("sldLayoutMkLst", "sldMasterMkLst", "sldLayoutMk", "sldMasterMk")}
            for node in anchor.iter()
        )
        for node in anchor.iter():
            if node.tag == _PC + "sldMk" and slide_id is None:
                slide_id = node.get("sldId")
            elif node.tag in _SHAPES and not template_target:
                # A group qualifies the path; the final non-group moniker
                # names the actual shape. Never guess from position or text.
                target = {}
                if node.tag != _OAC + "grpSpMk":
                    if identifier := node.get("id"):
                        target["drawingId"] = identifier
                    if creation := node.get("creationId"):
                        target["creationId"] = creation
    return slide_id, target


def matches_shape(target: CommentTarget, shape: ShapeBlock) -> bool:
    identifier = target.get("drawingId")
    creation = target.get("creationId")
    return bool(
        (identifier or creation)
        and (not identifier or identifier == shape.get("drawingId"))
        and (not creation or creation.casefold() == shape.get("creationId", "").casefold())
    )
