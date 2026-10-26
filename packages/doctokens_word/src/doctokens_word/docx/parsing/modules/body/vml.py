"""Read VML image references and text boxes in their saved source order."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ....model import AssetLookup, DrawingCommon, InlineObject
from ....ooxml.namespaces import attr, qualified_name
from .object_common import append_image_or_placeholder, copy_drawing_common
from .textboxes import TextboxReader, textbox_objects_from_nodes

_SHAPES = frozenset(
    qualified_name("v", name) for name in ("shape", "rect", "roundrect", "oval", "line", "polyline", "arc", "curve", "image")
)
_IMAGE_DATA = qualified_name("v", "imagedata")
_TEXTBOX = qualified_name("w", "txbxContent")


def pict_objects(
    pict: ET.Element, part: str, asset_lookup: AssetLookup, textbox_reader: TextboxReader | None = None
) -> list[InlineObject]:
    """Bind each image using its owner part and retain the shape's description.

    Traversal stops at text-box content: the existing text-box projection owns
    its paragraphs. Unresolved image references keep the normal drawing fallback.
    """
    objects: list[InlineObject] = []
    fallback_common: DrawingCommon = {"placement": "vml"}

    def walk(node: ET.Element, common: DrawingCommon) -> None:
        nonlocal fallback_common
        if node.tag in _SHAPES:
            common = _shape_common(node)
            fallback_common = common
        if node.tag == _IMAGE_DATA:
            image_common = common.copy()
            title = attr(node, "o", "title")
            if title and not image_common.get("title"):
                image_common["title"] = title
            alt = image_common.get("alt") or image_common.get("title") or image_common.get("name")
            if alt:
                image_common["alt"] = alt
            append_image_or_placeholder(objects, asset_lookup, part, attr(node, "r", "id") or "", image_common)
            return
        if node.tag == _TEXTBOX:
            objects.extend(textbox_objects_from_nodes([node], common, part, textbox_reader))
            return
        for child in node:
            walk(child, common)

    walk(pict, fallback_common)
    if not objects:
        placeholder: InlineObject = {"type": "drawing"}
        copy_drawing_common(placeholder, fallback_common)
        objects.append(placeholder)
    return objects


def _shape_common(shape: ET.Element) -> DrawingCommon:
    common: DrawingCommon = {"placement": "vml"}
    style = {
        key.strip().lower(): value.strip().lower()
        for item in (shape.get("style") or "").split(";")
        if ":" in item
        for key, value in [item.split(":", 1)]
    }
    if style.get("position", "").strip().lower() in {"absolute", "relative"}:
        common["placement"] = "anchor"
    for key, value in (("name", shape.get("id")), ("alt", shape.get("alt")), ("title", shape.get("title"))):
        if value:
            if key == "name":
                common["name"] = value
            elif key == "alt":
                common["alt"] = value
            else:
                common["title"] = value
    return common
