"""Count retained presentation content independently of output selections."""

from __future__ import annotations

from ..core.models import ParsedPresentation


def presentation_manifest(presentation: ParsedPresentation) -> dict[str, object]:
    images = [asset for asset in presentation.assets if asset.get("type") == "image"]
    media = [asset for asset in presentation.assets if asset.get("type") == "media"]
    return {
        "slideCount": len(presentation.slides),
        "shapeCount": sum(len(slide["shapes"]) for slide in presentation.slides),
        "imageCount": len(images),
        "mediaCount": len(media),
        "imageRelationshipCount": len(images),
        "imageUniqueTargetCount": len({(asset.get("source"), asset.get("zipPath") or asset.get("href")) for asset in images}),
        "mediaRelationshipCount": sum(asset.get("relationshipCount", 1) for asset in media),
        "chartCount": len(presentation.charts),
        "smartartCount": len(presentation.smartarts),
        "commentCount": len(presentation.comments),
    }
