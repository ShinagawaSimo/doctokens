"""Bind saved audio/video declarations without replacing their poster images."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from doctokens_core.models import ParseWarning

from ....core.constants import attr, qualified_name
from ....core.models import AssetLookup, ShapeBlock
from .shape_details import _shape_alt, _shape_name

_P14_MEDIA = "{http://schemas.microsoft.com/office/powerpoint/2010/main}media"
_VIDEO = {qualified_name(prefix, "videoFile") for prefix in ("a", "p")}
_AUDIO = {qualified_name(prefix, "audioFile") for prefix in ("a", "p")} | {qualified_name("a", "wavAudioFile")}


def media_shape(
    node: ET.Element, part: str, ordinal: int, assets: AssetLookup, warnings: list[ParseWarning], *, standalone: bool = False
) -> ShapeBlock | None:
    declarations = [item for item in node.iter() if item.tag in {_P14_MEDIA, *_VIDEO, *_AUDIO}]
    if not declarations and not standalone:
        return None
    kind = "media"
    if any(item.tag in _VIDEO for item in declarations):
        kind = "video"
    elif any(item.tag in _AUDIO for item in declarations):
        kind = "audio"
    shape: ShapeBlock = {"id": f"s{ordinal}", "type": "media", "name": _shape_name(node) or "", "kind": kind}
    if alt := _shape_alt(node):
        shape["alt"] = alt
    # Office's p14 extension is the preferred embedded target; legacy references
    # remain useful when that extension is absent, missing or dangling.
    ordered = sorted(declarations, key=lambda item: item.tag != _P14_MEDIA)
    references = [attr(item, "r", "embed") or attr(item, "r", "link") for item in ordered]
    if standalone and not references:
        references = [attr(node, "r", "embed") or attr(node, "r", "link")]
    for reference in references:
        asset = assets.get((part, reference)) if reference else None
        if asset is None or asset.get("type") != "media":
            continue
        shape["assetId"] = asset["id"]
        if kind == "media":
            content_type = asset.get("contentType", "")
            if content_type.startswith(("video/", "audio/")):
                shape["kind"] = content_type.split("/", 1)[0]
        if asset.get("source") == "external":
            shape["href"] = asset.get("href", "")
        return shape
    code = "MEDIA_ASSET_MISSING" if any(references) else "MEDIA_MISSING_RID"
    warnings.append(ParseWarning(code=code, message="Media declaration has no resolvable audio/video relationship", locator=part))
    return shape
