"""Extract non-text inline objects from WordprocessingML runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ....core.constants import attr, child_elements, first_child, local_name, qualified_name
from ....core.models import (
    AssetLookup,
    Chart,
    DrawingCommon,
    InlineObject,
    ObjectLookup,
    SmartArt,
)
from ....ooxml.omml_latex import omath_to_latex


@dataclass(slots=True)
class DrawingScanResult:
    """All reusable facts collected from one ``w:drawing`` subtree."""

    common: DrawingCommon
    chart_rel_ids: list[str] = field(default_factory=list)
    smartart_rel_ids: list[str] = field(default_factory=list)
    image_rel_id: str | None = None
    textbox_nodes: list[ET.Element] = field(default_factory=list)

    @classmethod
    def scan(cls, drawing: ET.Element) -> DrawingScanResult:
        candidates: list[tuple[str, DrawingCommon]] = []
        scan_result = cls({"placement": "drawing"})

        def walk(node: ET.Element, active: DrawingCommon | None) -> None:
            local = local_name(node.tag)
            if local in {"inline", "anchor"} and node.tag.startswith("{"):
                active = {"placement": local}
                candidates.append((local, active))
            if local == "chart":
                rel_id = attr(node, "r", "id")
                if rel_id:
                    scan_result.chart_rel_ids.append(rel_id)
            elif local == "relIds":
                rel_id = attr(node, "r", "dm")
                if rel_id:
                    scan_result.smartart_rel_ids.append(rel_id)
            elif local == "blip" and scan_result.image_rel_id is None:
                scan_result.image_rel_id = attr(node, "r", "embed")
            elif local == "txbxContent":
                scan_result.textbox_nodes.append(node)
            if active is not None:
                if local == "docPr":
                    name = node.get("name")
                    descr = node.get("descr")
                    title = node.get("title")
                    if name:
                        active["name"] = name
                    if descr:
                        active["alt"] = descr
                    if title:
                        active["title"] = title
                elif local == "extent" and "cx" not in active:
                    cx = node.get("cx")
                    cy = node.get("cy")
                    if cx is not None:
                        active["cx"] = cx
                    if cy is not None:
                        active["cy"] = cy
            for child in node:
                walk(child, active)

        walk(drawing, None)
        chosen = next((facts for kind, facts in candidates if kind == "inline"), None)
        if chosen is None and candidates:
            chosen = candidates[0][1]
        if chosen is not None:
            scan_result.common = chosen
        return scan_result


def equation_object(node: ET.Element) -> InlineObject:
    """Convert an OMML equation to a LaTeX string."""
    equation_text = omath_to_latex(node)
    return {"type": "equation", "text": equation_text}


def drawing_objects(
    drawing: ET.Element,
    part: str,
    asset_lookup: AssetLookup,
    object_lookup: ObjectLookup,
) -> list[InlineObject]:
    """Extract image references, text boxes, charts, SmartArt, and placeholders."""
    drawing_scan = DrawingScanResult.scan(drawing)
    drawing_common = drawing_scan.common
    inline_objects: list[InlineObject] = []

    inline_objects.extend(
        _referenced_object(object_lookup, part, rel_id, "chart", drawing_common) for rel_id in drawing_scan.chart_rel_ids
    )
    inline_objects.extend(
        _referenced_object(object_lookup, part, rel_id, "smartart", drawing_common) for rel_id in drawing_scan.smartart_rel_ids
    )

    image_relationship_id = drawing_scan.image_rel_id
    if image_relationship_id:
        _append_image_or_placeholder(inline_objects, asset_lookup, part, image_relationship_id, drawing_common)

    inline_objects.extend(_textbox_objects_from_nodes(drawing_scan.textbox_nodes, drawing_common))
    if inline_objects:
        return inline_objects

    fallback_object: InlineObject = {"type": "drawing"}
    _copy_drawing_common(fallback_object, drawing_common)
    return [fallback_object]


def pict_objects(pict: ET.Element) -> list[InlineObject]:
    """Extract text boxes from legacy VML pict; keep placeholders for other shapes."""
    inline_objects: list[InlineObject] = []
    drawing_common: DrawingCommon = {"placement": "vml"}
    for shape in pict.iter(qualified_name("v", "shape")):
        shape_id = shape.get("id")
        alt = shape.get("alt")
        if shape_id:
            drawing_common["name"] = shape_id
        if alt:
            drawing_common["alt"] = alt

    inline_objects.extend(_textbox_objects(pict, drawing_common))
    if inline_objects:
        return inline_objects

    drawing_object: InlineObject = {"type": "drawing"}
    _copy_drawing_common(drawing_object, drawing_common)
    return [drawing_object]


def parse_embedded_object(obj_elem: ET.Element) -> InlineObject:
    """Extract the embedded object type from a w:object element."""
    embedded_object: InlineObject = {"type": "embedded"}
    ole = first_child(obj_elem, "o", "OLEObject")
    if ole is not None:
        progid = ole.get("ProgID", "")
        if progid:
            embedded_object["embeddedType"] = _progid_to_type(progid)
            embedded_object["progid"] = progid
    if "embeddedType" not in embedded_object:
        embedded_object["embeddedType"] = "unknown"

    for shape in obj_elem.iter(qualified_name("v", "shape")):
        title = shape.get("title") or shape.get("alt")
        if title:
            embedded_object["name"] = title
            break
    if "name" not in embedded_object:
        for doc_pr in obj_elem.iter(qualified_name("wp", "docPr")):
            name = doc_pr.get("name")
            if name:
                embedded_object["name"] = name
                break
    return embedded_object


def _append_image_or_placeholder(
    objects: list[InlineObject],
    asset_lookup: AssetLookup,
    part: str,
    rel_id: str,
    common: DrawingCommon,
) -> None:
    asset = asset_lookup.get((part, rel_id))
    if asset is None:
        drawing_object: InlineObject = {"type": "drawing"}
        _copy_drawing_common(drawing_object, common)
        objects.append(drawing_object)
        return

    image: InlineObject = {"type": "image"}
    _copy_drawing_common(image, common)
    image["assetId"] = asset["id"]
    if "href" in asset:
        image["href"] = asset["href"]
    objects.append(image)


def _textbox_objects(node: ET.Element, common: DrawingCommon) -> list[InlineObject]:
    return _textbox_objects_from_nodes(_textbox_content_nodes(node), common)


def _textbox_objects_from_nodes(nodes: list[ET.Element], common: DrawingCommon) -> list[InlineObject]:
    objects: list[InlineObject] = []
    for txbx in nodes:
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


def _copy_drawing_common(inline_object: InlineObject, drawing_common: DrawingCommon) -> None:
    if "placement" in drawing_common:
        inline_object["placement"] = drawing_common["placement"]
    if "name" in drawing_common:
        inline_object["name"] = drawing_common["name"]
    if "alt" in drawing_common:
        inline_object["alt"] = drawing_common["alt"]
    if "title" in drawing_common:
        inline_object["title"] = drawing_common["title"]
    if "cx" in drawing_common:
        inline_object["cx"] = drawing_common["cx"]
    if "cy" in drawing_common:
        inline_object["cy"] = drawing_common["cy"]


def _object_from_lookup(parsed_object: Chart | SmartArt) -> InlineObject:
    inline_object: InlineObject = {
        "type": parsed_object["type"],
        "id": parsed_object["id"],
        "part": parsed_object["part"],
    }
    if parsed_object["type"] == "chart":
        inline_object["chartType"] = parsed_object["chartType"]
        inline_object["seriesCount"] = parsed_object["seriesCount"]
        inline_object["pointCount"] = parsed_object["pointCount"]
        inline_object["series"] = parsed_object["series"]
        if "title" in parsed_object:
            inline_object["title"] = parsed_object["title"]
        if "plots" in parsed_object:
            inline_object["plots"] = parsed_object["plots"]
    else:
        inline_object["nodeCount"] = parsed_object["nodeCount"]
        inline_object["linkCount"] = parsed_object["linkCount"]
        inline_object["rawLinkCount"] = parsed_object["rawLinkCount"]
        inline_object["nodes"] = parsed_object["nodes"]
        inline_object["links"] = parsed_object["links"]
        if "layoutType" in parsed_object:
            inline_object["layoutType"] = parsed_object["layoutType"]
    if "sourcePart" in parsed_object:
        inline_object["sourcePart"] = parsed_object["sourcePart"]
    if "relationshipId" in parsed_object:
        inline_object["relationshipId"] = parsed_object["relationshipId"]
    return inline_object


def _drawing_container(drawing: ET.Element) -> tuple[str, ET.Element | None]:
    inline = drawing.find(".//" + qualified_name("wp", "inline"))
    anchor = drawing.find(".//" + qualified_name("wp", "anchor"))
    if inline is not None:
        return ("inline", inline)
    if anchor is not None:
        return ("anchor", anchor)
    return ("drawing", None)


def _drawing_common_attrs(container: ET.Element | None, placement: str) -> DrawingCommon:
    drawing_common: DrawingCommon = {"placement": placement}
    if container is None:
        return drawing_common

    doc_pr = container.find(".//" + qualified_name("wp", "docPr"))
    if doc_pr is not None:
        name = doc_pr.get("name")
        descr = doc_pr.get("descr")
        title = doc_pr.get("title")
        if name:
            drawing_common["name"] = name
        if descr:
            drawing_common["alt"] = descr
        if title:
            drawing_common["title"] = title

    extent = first_child(container, "wp", "extent")
    if extent is not None:
        cx = extent.get("cx")
        cy = extent.get("cy")
        if cx is not None:
            drawing_common["cx"] = cx
        if cy is not None:
            drawing_common["cy"] = cy
    return drawing_common


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
