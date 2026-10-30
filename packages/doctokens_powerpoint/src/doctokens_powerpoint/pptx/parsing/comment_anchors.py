"""Saved comment monikers and exact identity matching, independent of geometry."""

from __future__ import annotations

from collections.abc import Iterator
from xml.etree import ElementTree as ET

from ..model.presentation import CommentAnchor, ShapeBlock

MODERN_NS = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"
_PC = "http://schemas.microsoft.com/office/powerpoint/2013/main/command"
_OAC = "http://schemas.microsoft.com/office/drawing/2013/main/command"
_ANCHORS = (
    {f"{{{_PC}}}{name}" for name in ("sldMkLst", "sldLayoutMkLst", "sldMasterMkLst")}
    | {f"{{{_OAC}}}{name}" for name in ("deMkLst", "txBodyMkLst", "txMkLst", "tcMkLst", "trMkLst", "gridColMkLst")}
    | {f"{{{MODERN_NS}}}unknownAnchor"}
)
_SHAPE_MONIKERS = {"spMk", "picMk", "cxnSpMk", "graphicFrameMk", "inkMk", "grpSpMk"}


def read_anchors(comment: ET.Element) -> list[CommentAnchor]:
    return [_anchor(child) for child in comment if child.tag in _ANCHORS]


def _anchor(node: ET.Element) -> CommentAnchor:
    namespace, _, kind = node.tag.removeprefix("{").partition("}")
    return {"kind": kind, "namespace": namespace, "attributes": dict(node.attrib), "children": [_anchor(child) for child in node]}


def walk_anchors(anchors: list[CommentAnchor]) -> Iterator[CommentAnchor]:
    for anchor in anchors:
        yield anchor
        yield from walk_anchors(anchor["children"])


def matches_shape(anchors: list[CommentAnchor], shape: ShapeBlock) -> bool:
    targets = [node for node in walk_anchors(anchors) if node["namespace"] == _OAC and node["kind"] in _SHAPE_MONIKERS]
    if not targets:
        return False
    # The final drawing moniker names the target; ancestor groups only qualify its path.
    target = targets[-1]
    if target["kind"] == "grpSpMk":
        return False
    attributes = target["attributes"]
    identifier = attributes.get("id")
    creation = attributes.get("creationId")
    return bool(
        (identifier or creation)
        and (not identifier or identifier == shape.get("drawingId"))
        and (not creation or creation.casefold() == shape.get("creationId", "").casefold())
    )
