"""Shape details."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.text.descriptions import first_readable
from doctokens_core.text.object_names import reading_object_name

from ....model.presentation import ShapeBlock
from ....ooxml.namespaces import local_name


def _is_meaningful_shape(shape: ShapeBlock) -> bool:
    return bool(
        shape.get("alt")
        or shape.get("title")
        or shape.get("link")
        or shape.get("fromShape")
        or shape.get("toShape")
        or shape.get("headEnd")
        or shape.get("tailEnd")
        or shape.get("commentAnchor")
    )


def _resolve_connector_endpoints(
    shapes: list[ShapeBlock],
    drawing_id_to_shape_id: dict[str, str],
) -> None:
    for shape in shapes:
        if shape.get("kind") != "connector":
            continue
        from_drawing_id = shape.get("fromShape")
        if from_drawing_id is not None:
            from_shape_id = drawing_id_to_shape_id.get(from_drawing_id)
            if from_shape_id is None:
                shape.pop("fromShape", None)
            else:
                shape["fromShape"] = from_shape_id
        to_drawing_id = shape.get("toShape")
        if to_drawing_id is not None:
            to_shape_id = drawing_id_to_shape_id.get(to_drawing_id)
            if to_shape_id is None:
                shape.pop("toShape", None)
            else:
                shape["toShape"] = to_shape_id


def _filter_decorative_shapes(shapes: list[ShapeBlock]) -> None:
    """Keep a connector's endpoints, but omit otherwise inert drawing marks."""
    connector_endpoints = {
        endpoint
        for shape in shapes
        if shape.get("kind") == "connector" and _is_meaningful_shape(shape)
        for endpoint in (shape.get("fromShape"), shape.get("toShape"))
        if endpoint is not None
    }
    shapes[:] = [
        shape for shape in shapes if shape["type"] != "shape" or _is_meaningful_shape(shape) or shape["id"] in connector_endpoints
    ]


def _geometric_key(shape: ShapeBlock) -> tuple[int, int]:
    y = shape.get("y")
    x = shape.get("x")
    if y is None or x is None:
        return (2**31, 0)
    return (y, x)


def _renumber_shapes(shapes: list[ShapeBlock]) -> None:
    """Keep compact, contiguous IR IDs after density-driven decoration filtering."""
    replacement_ids = {shape["id"]: f"s{index}" for index, shape in enumerate(shapes, start=1)}
    for shape in shapes:
        shape["id"] = replacement_ids[shape["id"]]
        if from_shape := shape.get("fromShape"):
            shape["fromShape"] = replacement_ids.get(from_shape, from_shape)
        if to_shape := shape.get("toShape"):
            shape["toShape"] = replacement_ids.get(to_shape, to_shape)


def _shape_name(shape: ET.Element, *, placeholder_type: str | None = None) -> str | None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    if c_nv_pr is None:
        return None
    name = c_nv_pr.get("name")
    if not name:
        return name
    namespace = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    if not shape.tag.startswith(namespace) or c_nv_pr.tag != namespace + "cNvPr":
        return name
    prefixes: set[str] = set()
    kind = local_name(shape.tag)
    if kind == "grpSp":
        prefixes.add("Group")
    elif kind == "pic":
        prefixes.add("Picture")
    elif kind in {"sp", "cxnSp"}:
        geometry = _geometry_type(shape)
        if kind == "sp":
            if geometry is not None or _find_descendant(shape, "custGeom") is not None:
                prefixes.add("AutoShape")
            if _find_descendant(shape, "custGeom") is not None:
                prefixes.add("Freeform")
            if _find_descendant(shape, "txBody") is not None and geometry in {None, "rect"}:
                prefixes.update(("Text Box", "TextBox"))
        geometry_prefixes = {"rect": "Rectangle", "roundRect": "Rounded Rectangle", "ellipse": "Oval", "line": "Line"}
        if geometry in geometry_prefixes:
            prefixes.add(geometry_prefixes[geometry])
        if kind == "cxnSp" and geometry == "line":
            prefixes.add("Straight Connector")
    elif kind == "graphicFrame":
        data = _find_descendant(shape, "graphicData")
        uri = data.get("uri", "") if data is not None else ""
        families = {
            "http://schemas.openxmlformats.org/drawingml/2006/chart": "Chart",
            "http://schemas.microsoft.com/office/drawing/2014/chartex": "Chart",
            "http://schemas.openxmlformats.org/drawingml/2006/table": "Table",
            "http://schemas.openxmlformats.org/drawingml/2006/diagram": "Diagram",
        }
        if uri in families:
            prefixes.add(families[uri])
    placeholder = _find_descendant(shape, "ph")
    if placeholder is not None:
        prefixes.add("Placeholder")
        effective_type = placeholder_type or placeholder.get("type")
        if effective_type in {"title", "ctrTitle"}:
            prefixes.add("Title")
        elif effective_type == "sldNum":
            prefixes.add("Slide Number Placeholder")
    return reading_object_name(name, prefixes)


def _shape_alt(shape: ET.Element) -> str | None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    if c_nv_pr is None:
        return None
    descr = c_nv_pr.get("descr")
    title = c_nv_pr.get("title")
    return first_readable(descr, title)


def _geometry_type(shape: ET.Element) -> str | None:
    geometry = _find_descendant(shape, "prstGeom")
    return geometry.get("prst") if geometry is not None else None


def _drawing_id(shape: ET.Element) -> str | None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    return c_nv_pr.get("id") if c_nv_pr is not None else None


def _attach_accessibility(result: ShapeBlock, shape: ET.Element) -> None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    if c_nv_pr is None:
        return
    if result["type"] == "picture":
        if description := first_readable(c_nv_pr.get("descr"), result.get("alt"), c_nv_pr.get("title")):
            result["alt"] = description
        return
    if description := first_readable(c_nv_pr.get("descr")):
        result["alt"] = description
    if title := first_readable(c_nv_pr.get("title")):
        result["title"] = title


def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
    for descendant in element.iter():
        if local_name(descendant.tag) == local:
            return descendant
    return None
