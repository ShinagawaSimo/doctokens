"""Asset indexing — builds (sourcePart, rId) → asset lookup without extracting binary data."""

from __future__ import annotations

import mimetypes

from ooxml_llm_core.models import ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from ....core.models import AssetLookup, ImageAsset
from ....core.package import PackageReader

IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
MEDIA_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/media"

_INDEX_TYPES = {
    IMAGE_REL_TYPE: ("image", "img"),
    MEDIA_REL_TYPE: ("media", "media"),
}


class AssetExtractor:
    """Index embedded/external images and media. Binary retrieval is on-demand."""

    def __init__(
        self,
        package_reader: PackageReader,
        relationships: RelationshipIndex,
        warnings: list[ParseWarning],
    ) -> None:
        self._package_reader = package_reader
        self._relationships = relationships
        self._warnings = warnings
        self._content_types = package_reader.read_content_types()

    def extract(self) -> tuple[list[ImageAsset], AssetLookup]:
        assets: list[ImageAsset] = []
        lookup: AssetLookup = {}
        counters: dict[str, int] = {}
        for rel_type, (asset_type, id_prefix) in _INDEX_TYPES.items():
            for record in self._relationships.by_type(rel_type):
                counters[id_prefix] = counters.get(id_prefix, 0) + 1
                asset_id = f"{id_prefix}{counters[id_prefix]}"
                if record.target_mode == "External":
                    asset: ImageAsset = {
                        "id": asset_id,
                        "type": asset_type,
                        "source": "external",
                        "href": record.target,
                    }
                else:
                    zip_path = record.resolved_target
                    if zip_path is None or not self._package_reader.exists(zip_path):
                        self._warnings.append(
                            ParseWarning(
                                code="ASSET_PART_MISSING",
                                message=f"Asset part missing: {zip_path}",
                                locator=record.source_part,
                            )
                        )
                        continue
                    asset = {
                        "id": asset_id,
                        "type": asset_type,
                        "source": "embedded",
                        "zipPath": zip_path,
                        "contentType": self._content_type_for_part(zip_path),
                    }
                assets.append(asset)
                lookup[(record.source_part, record.id)] = asset
        return assets, lookup

    def _content_type_for_part(self, zip_path: str) -> str:
        if zip_path in self._content_types["overrides"]:
            return self._content_types["overrides"][zip_path]
        ext = zip_path.rsplit(".", 1)[-1].lower() if "." in zip_path else ""
        if ext and ext in self._content_types["defaults"]:
            return self._content_types["defaults"][ext]
        return mimetypes.guess_type(zip_path)[0] or "application/octet-stream"
