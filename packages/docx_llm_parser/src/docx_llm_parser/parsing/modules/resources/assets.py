"""Build the image resource index. No binary data is extracted -- fetched on demand via get_resource."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ....core.models import AssetLookup, ContentTypes, ImageAsset, ParseWarning
from ....core.package import PackageReader
from ....core.relationships import RelationshipIndex

IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


class AssetExtractor:
    """Scan image relationships and build a (sourcePart, rId) -> asset index."""

    def __init__(
        self,
        package: PackageReader,
        relationships: RelationshipIndex,
        content_types: ContentTypes,
        warnings: list[ParseWarning],
    ) -> None:
        self.package = package
        self.relationships = relationships
        self.content_types = content_types
        self.warnings = warnings

    def extract(self) -> tuple[list[ImageAsset], AssetLookup]:
        """Build the image metadata index without reading binary data."""
        assets: list[ImageAsset] = []
        lookup: AssetLookup = {}
        image_index = 1
        for rel in self.relationships.by_type(IMAGE_REL_TYPE):
            if rel.target_mode == "External":
                external_asset: ImageAsset = {
                    "id": f"img{image_index}",
                    "type": "image",
                    "source": "external",
                    "href": rel.target,
                }
                image_index += 1
                assets.append(external_asset)
                lookup[(rel.source_part, rel.id)] = external_asset
                continue

            target = rel.resolved_target
            if not target or not self.package.exists(target):
                self.warnings.append(
                    ParseWarning(
                        code="IMAGE_TARGET_MISSING",
                        message=f"Image target is missing: {target}",
                        locator=rel.source_part,
                    )
                )
                continue

            asset_id = f"img{image_index}"
            image_index += 1
            content_type = self._content_type_for_part(target)

            embedded_asset: ImageAsset = {
                "id": asset_id,
                "type": "image",
                "source": "embedded",
                "zipPath": target,
            }
            if content_type is not None:
                embedded_asset["contentType"] = content_type
            assets.append(embedded_asset)
            lookup[(rel.source_part, rel.id)] = embedded_asset
        return assets, lookup

    def _content_type_for_part(self, part_name: str) -> str | None:
        """Infer the resource MIME type from Content Types."""
        overrides = self.content_types["overrides"]
        defaults = self.content_types["defaults"]
        if part_name in overrides:
            return overrides[part_name]
        ext = Path(part_name).suffix.lstrip(".").lower()
        if ext in defaults:
            return defaults[ext]
        guessed, _ = mimetypes.guess_type(part_name)
        return guessed
