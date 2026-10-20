"""Bind inline images to the DOCX resource index and copy shared drawing metadata."""

from __future__ import annotations

from ....core.models import AssetLookup, DrawingCommon, InlineObject


def append_image_or_placeholder(
    objects: list[InlineObject],
    asset_lookup: AssetLookup,
    part: str,
    rel_id: str,
    common: DrawingCommon,
) -> None:
    asset = asset_lookup.get((part, rel_id))
    if asset is None:
        drawing_object: InlineObject = {"type": "drawing"}
        copy_drawing_common(drawing_object, common)
        objects.append(drawing_object)
        return

    image: InlineObject = {"type": "image"}
    copy_drawing_common(image, common)
    image["assetId"] = asset["id"]
    if "href" in asset:
        image["href"] = asset["href"]
    objects.append(image)


def copy_drawing_common(inline_object: InlineObject, drawing_common: DrawingCommon) -> None:
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
