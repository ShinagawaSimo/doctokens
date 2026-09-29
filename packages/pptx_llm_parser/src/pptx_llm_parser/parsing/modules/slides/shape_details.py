"""Shape details."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....core.constants import local_name
from ....core.models import (
    ShapeBlock,
)


def _is_meaningful_shape(shape: ShapeBlock) -> bool:
    return bool(shape.get("alt") or shape.get("title") or shape.get("link") or shape.get("fromShape") or shape.get("toShape"))


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


def _shape_name(shape: ET.Element) -> str | None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    return c_nv_pr.get("name") if c_nv_pr is not None else None


def _shape_alt(shape: ET.Element) -> str | None:
    c_nv_pr = _find_descendant(shape, "cNvPr")
    if c_nv_pr is None:
        return None
    descr = c_nv_pr.get("descr")
    title = c_nv_pr.get("title")
    return descr or title or None


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
    if description := c_nv_pr.get("descr"):
        result["alt"] = description
    if title := c_nv_pr.get("title"):
        result["title"] = title


def _find_descendant(element: ET.Element, local: str) -> ET.Element | None:
    for descendant in element.iter():
        if local_name(descendant.tag) == local:
            return descendant
    return None
