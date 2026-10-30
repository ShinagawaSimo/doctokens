"""Select supported shape and math alternatives using original namespace scopes."""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning
from doctokens_core.ooxml.charts.parser import CHART_EX_GRAPHIC_DATA_URI

from .math import _SUPPORTED as _MATH_NAMESPACES
from .math import normalize_math
from .namespaces import NS, first_child
from .package import PackageReader
from .unsupported import unparsed_element

_ALTERNATE = f"{{{NS['mc']}}}AlternateContent"
_CHOICE = f"{{{NS['mc']}}}Choice"
_FALLBACK = f"{{{NS['mc']}}}Fallback"
_P = f"{{{NS['p']}}}"
_CONTAINERS = {_P + "spTree", _P + "grpSp"}
_SHAPES = {_P + name for name in ("sp", "pic", "graphicFrame", "cxnSp", "grpSp")}
_SHAPE_NAMESPACES = _MATH_NAMESPACES | {
    NS["p"],
    NS["c"],
    NS["dgm"],
    "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "http://schemas.microsoft.com/office/drawing/2014/chartex",
}
_GRAPHICS = {
    "http://schemas.openxmlformats.org/drawingml/2006/table",
    "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "http://schemas.openxmlformats.org/presentationml/2006/ole",
    CHART_EX_GRAPHIC_DATA_URI,
}


def read_content_part(package: PackageReader, part: str, warnings: list[ParseWarning]) -> ET.Element:
    """Read once; record namespace capability separately for both dispatch layers."""
    bindings: dict[str, str] = {}
    pending: list[tuple[str, str]] = []
    stack: list[list[tuple[str, str | None]]] = []
    math_choices: set[ET.Element] = set()
    shape_choices: set[ET.Element] = set()
    root: ET.Element | None = None
    with package.open_entry(part) as stream:
        for event, item in ET.iterparse(stream, events=("start-ns", "start", "end")):
            if event == "start-ns":
                pending.append(cast(tuple[str, str], item))
                continue
            node = cast(ET.Element, item)
            if event == "start":
                stack.append([(prefix, bindings.get(prefix)) for prefix, _ in pending])
                bindings.update(pending)
                pending.clear()
                if node.tag == _CHOICE:
                    required = node.get("Requires", "").split()
                    if required and all(bindings.get(prefix) in _MATH_NAMESPACES for prefix in required):
                        math_choices.add(node)
                    if required and all(bindings.get(prefix) in _SHAPE_NAMESPACES for prefix in required):
                        shape_choices.add(node)
            else:
                for prefix, uri in stack.pop():
                    if uri is None:
                        bindings.pop(prefix, None)
                    else:
                        bindings[prefix] = uri
                root = node
    if root is None:
        raise ET.ParseError("empty XML part")
    _normalize_shapes(root, shape_choices, warnings, part)
    normalize_math(root, math_choices, warnings, part)
    return root


def _select_shapes(alternate: ET.Element, supported: set[ET.Element]) -> list[ET.Element] | None:
    for branch in alternate:
        if branch.tag == _CHOICE and branch in supported:
            result = _shape_children(branch, supported)
            if result is not None:
                return result
    fallback = next((node for node in alternate if node.tag == _FALLBACK), None)
    return _shape_children(fallback, supported) if fallback is not None else None


def _shape_children(container: ET.Element, supported: set[ET.Element]) -> list[ET.Element] | None:
    result: list[ET.Element] = []
    for node in container:
        if node.tag == _ALTERNATE:
            nested = _select_shapes(node, supported)
            if nested is None:
                return None
            result.extend(nested)
        elif not _readable_shape(node, supported):
            return None
        else:
            result.append(node)
    return result


def _readable_shape(node: ET.Element, supported: set[ET.Element]) -> bool:
    if node.tag not in _SHAPES:
        return False
    if node.tag == _P + "graphicFrame":
        graphic = first_child(node, "a", "graphic")
        data = first_child(graphic, "a", "graphicData") if graphic is not None else None
        return data is not None and data.get("uri") in _GRAPHICS
    if node.tag == _P + "grpSp":
        for child in node:
            if child.tag in {_P + "nvGrpSpPr", _P + "grpSpPr", _P + "extLst"}:
                continue
            if child.tag == _ALTERNATE:
                if _select_shapes(child, supported) is None:
                    return False
            elif not _readable_shape(child, supported):
                return False
    return True


def _normalize_shapes(
    node: ET.Element,
    supported: set[ET.Element],
    warnings: list[ParseWarning],
    part: str,
) -> None:
    if node.tag == _ALTERNATE:
        return
    if node.tag in _CONTAINERS:
        children: list[ET.Element] = []
        for child in node:
            if child.tag == _ALTERNATE:
                selected = _select_shapes(child, supported)
                if selected is None:
                    warnings.append(
                        ParseWarning(
                            "SHAPE_ALTERNATE_CONTENT_UNSUPPORTED",
                            "Shape has no readable Choice or Fallback",
                            part,
                        )
                    )
                    children.append(unparsed_element("AlternateContent"))
                    continue
                children.extend(selected)
            else:
                children.append(child)
        node[:] = children
    for child in node:
        _normalize_shapes(child, supported, warnings, part)
