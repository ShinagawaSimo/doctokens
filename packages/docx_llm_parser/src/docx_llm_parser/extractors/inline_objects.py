"""Extract non-text inline objects from WordprocessingML runs."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..core.constants import attr, child_elements, first_child, local_name, qualified_name
from ..core.models import (
    AssetLookup,
    Chart,
    DrawingCommon,
    InlineObject,
    ObjectLookup,
    SmartArt,
)
from ..ooxml.omml_latex import omath_to_latex


def equation_object(node: ET.Element) -> InlineObject:
    """Convert an OMML equation to a LaTeX string."""
    text = omath_to_latex(node)
    return {"type": "equation", "text": text}


def drawing_objects(
    drawing: ET.Element,
    part: str,
    asset_lookup: AssetLookup,
    object_lookup: ObjectLookup,
) -> list[InlineObject]:
    """Extract image references, text boxes, charts, SmartArt, and placeholders."""
    placement, container = _drawing_container(drawing)
    common = _drawing_common_attrs(container, placement)
    objects: list[InlineObject] = []

    for chart in drawing.iter(qualified_name("c", "chart")):
        rel_id = attr(chart, "r", "id")
        if rel_id:
            objects.append(_referenced_object(object_lookup, part, rel_id, "chart", common))

    for rel_ids in drawing.iter(qualified_name("dgm", "relIds")):
        rel_id = attr(rel_ids, "r", "dm")
        if rel_id:
            objects.append(_referenced_object(object_lookup, part, rel_id, "smartart", common))

    blip = drawing.find(".//" + qualified_name("a", "blip"))
    rel_id = attr(blip, "r", "embed") if blip is not None else None
    if rel_id:
        _append_image_or_placeholder(objects, asset_lookup, part, rel_id, common)

    objects.extend(_textbox_objects(drawing, common))
    if objects:
        return objects

    fallback_obj: InlineObject = {"type": "drawing"}
    _copy_drawing_common(fallback_obj, common)
    return [fallback_obj]


def pict_objects(pict: ET.Element) -> list[InlineObject]:
    """Extract text boxes from legacy VML pict; keep placeholders for other shapes."""
    objects: list[InlineObject] = []
    common: DrawingCommon = {"placement": "vml"}
    for shape in pict.iter(qualified_name("v", "shape")):
        shape_id = shape.get("id")
        alt = shape.get("alt")
        if shape_id:
            common["name"] = shape_id
        if alt:
            common["alt"] = alt

    objects.extend(_textbox_objects(pict, common))
    if objects:
        return objects

    drawing: InlineObject = {"type": "drawing"}
    _copy_drawing_common(drawing, common)
    return [drawing]


def parse_embedded_object(obj_elem: ET.Element) -> InlineObject:
    """Extract the embedded object type from a w:object element."""
    result: InlineObject = {"type": "embedded"}
    ole = first_child(obj_elem, "o", "OLEObject")
    if ole is not None:
        progid = ole.get("ProgID", "")
        if progid:
            result["embeddedType"] = _progid_to_type(progid)
            result["progid"] = progid
    if "embeddedType" not in result:
        result["embeddedType"] = "unknown"

    for shape in obj_elem.iter(qualified_name("v", "shape")):
        title = shape.get("title") or shape.get("alt")
        if title:
            result["name"] = title
            break
    if "name" not in result:
        for doc_pr in obj_elem.iter(qualified_name("wp", "docPr")):
            name = doc_pr.get("name")
            if name:
                result["name"] = name
                break
    return result


def _append_image_or_placeholder(
    objects: list[InlineObject],
    asset_lookup: AssetLookup,
    part: str,
    rel_id: str,
    common: DrawingCommon,
) -> None:
    asset = asset_lookup.get((part, rel_id))
    if asset is None:
        drawing_obj: InlineObject = {"type": "drawing"}
        _copy_drawing_common(drawing_obj, common)
        objects.append(drawing_obj)
        return

    image: InlineObject = {"type": "image"}
    _copy_drawing_common(image, common)
    image["assetId"] = asset["id"]
    if "file" in asset:
        image["file"] = asset["file"]
    if "href" in asset:
        image["href"] = asset["href"]
    objects.append(image)


def _textbox_objects(node: ET.Element, common: DrawingCommon) -> list[InlineObject]:
    objects: list[InlineObject] = []
    for txbx in _textbox_content_nodes(node):
        text = _container_plain_text(txbx)
        if text.strip():
            textbox: InlineObject = {"type": "textbox", "text": text}
            _copy_drawing_common(textbox, common)
            objects.append(textbox)
    return objects


def _referenced_object(
    object_lookup: ObjectLookup,
    part: str,
    rel_id: str,
    fallback_type: str,
    common: DrawingCommon,
) -> InlineObject:
    parsed = object_lookup.get((part, rel_id))
    if parsed is None:
        obj: InlineObject = {"type": fallback_type, "id": rel_id}
        _copy_drawing_common(obj, common)
        return obj
    obj = _object_from_lookup(parsed)
    _copy_drawing_common(obj, common)
    return obj


def _copy_drawing_common(obj: InlineObject, common: DrawingCommon) -> None:
    if "placement" in common:
        obj["placement"] = common["placement"]
    if "name" in common:
        obj["name"] = common["name"]
    if "alt" in common:
        obj["alt"] = common["alt"]
    if "title" in common:
        obj["title"] = common["title"]
    if "cx" in common:
        obj["cx"] = common["cx"]
    if "cy" in common:
        obj["cy"] = common["cy"]


def _object_from_lookup(parsed: Chart | SmartArt) -> InlineObject:
    obj: InlineObject = {
        "type": parsed["type"],
        "id": parsed["id"],
        "part": parsed["part"],
    }
    if parsed["type"] == "chart":
        obj["chartType"] = parsed["chartType"]
        obj["seriesCount"] = parsed["seriesCount"]
        obj["pointCount"] = parsed["pointCount"]
        obj["series"] = parsed["series"]
        if "title" in parsed:
            obj["title"] = parsed["title"]
    else:
        obj["nodeCount"] = parsed["nodeCount"]
        obj["linkCount"] = parsed["linkCount"]
        obj["rawLinkCount"] = parsed["rawLinkCount"]
        obj["nodes"] = parsed["nodes"]
        obj["links"] = parsed["links"]
        if "layoutType" in parsed:
            obj["layoutType"] = parsed["layoutType"]
    if "sourcePart" in parsed:
        obj["sourcePart"] = parsed["sourcePart"]
    if "relationshipId" in parsed:
        obj["relationshipId"] = parsed["relationshipId"]
    return obj


def _drawing_container(drawing: ET.Element) -> tuple[str, ET.Element | None]:
    inline = drawing.find(".//" + qualified_name("wp", "inline"))
    anchor = drawing.find(".//" + qualified_name("wp", "anchor"))
    if inline is not None:
        return ("inline", inline)
    if anchor is not None:
        return ("anchor", anchor)
    return ("drawing", None)


def _drawing_common_attrs(container: ET.Element | None, placement: str) -> DrawingCommon:
    obj: DrawingCommon = {"placement": placement}
    if container is None:
        return obj

    doc_pr = container.find(".//" + qualified_name("wp", "docPr"))
    if doc_pr is not None:
        name = doc_pr.get("name")
        descr = doc_pr.get("descr")
        title = doc_pr.get("title")
        if name:
            obj["name"] = name
        if descr:
            obj["alt"] = descr
        if title:
            obj["title"] = title

    extent = first_child(container, "wp", "extent")
    if extent is not None:
        cx = extent.get("cx")
        cy = extent.get("cy")
        if cx is not None:
            obj["cx"] = cx
        if cy is not None:
            obj["cy"] = cy
    return obj


def _textbox_content_nodes(node: ET.Element) -> list[ET.Element]:
    return list(node.iter(qualified_name("w", "txbxContent")))


def _container_plain_text(node: ET.Element) -> str:
    parts: list[str] = []
    for child in node:
        lname = local_name(child.tag)
        if lname == "p":
            text = _inline_plain_text(child)
        elif lname == "tbl":
            text = _table_plain_text(child)
        else:
            text = _inline_plain_text(child)
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _table_plain_text(tbl: ET.Element) -> str:
    rows: list[str] = []
    for tr in child_elements(tbl, "w", "tr"):
        cells = [_container_plain_text(tc) for tc in child_elements(tr, "w", "tc")]
        row = " | ".join(cell.strip() for cell in cells if cell.strip())
        if row:
            rows.append(row)
    return "\n".join(rows)


def _inline_plain_text(node: ET.Element) -> str:
    parts: list[str] = []
    for item in node.iter():
        lname = local_name(item.tag)
        if lname == "t":
            parts.append(item.text or "")
        elif lname == "tab":
            parts.append("\t")
        elif lname in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts)


def _progid_to_type(progid: str) -> str:
    progid_lower = progid.lower()
    if "excel" in progid_lower:
        return "excel"
    if "word" in progid_lower:
        return "word"
    if "powerpoint" in progid_lower:
        return "powerpoint"
    if "acroexch" in progid_lower:
        return "pdf"
    if "visio" in progid_lower:
        return "visio"
    if "paint" in progid_lower:
        return "image"
    if "package" in progid_lower:
        return "package"
    return "unknown"
