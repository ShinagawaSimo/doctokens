"""提取 DOCX 中可供 LLM 引用的媒体资源。"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ..core.models import ParseWarning
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex


IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


class AssetExtractor:
    """从 relationships 中识别图片，并按需导出到 assets 目录。"""

    def __init__(
        self,
        package: PackageReader,
        relationships: RelationshipIndex,
        content_types: dict,
        output_dir: Path,
        warnings: list[ParseWarning],
    ) -> None:
        self.package = package
        self.relationships = relationships
        self.content_types = content_types
        self.output_dir = output_dir
        self.warnings = warnings

    def extract(self) -> tuple[list[dict], dict[tuple[str, str], dict]]:
        """导出图片资源，并返回 relationship 到 asset 的索引。"""
        assets_dir = self.output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        assets: list[dict] = []
        lookup: dict[tuple[str, str], dict] = {}
        image_index = 1
        for rel in self.relationships.by_type(IMAGE_REL_TYPE):
            if rel.target_mode == "External":
                # 外链图片不下载，只把 URL 作为可引用资源记录下来。
                asset = {
                    "id": f"img{image_index}",
                    "type": "image",
                    "source": "external",
                    "href": rel.target,
                    "relationshipId": rel.id,
                    "sourcePart": rel.source_part,
                }
                image_index += 1
                assets.append(asset)
                lookup[(rel.source_part, rel.id)] = asset
                continue

            target = rel.resolved_target
            if not target or not self.package.exists(target):
                # 关系存在但资源缺失时继续解析正文，给 debug 留 warning。
                self.warnings.append(
                    ParseWarning(
                        level="warning",
                        code="IMAGE_TARGET_MISSING",
                        message=f"Image target is missing: {target}",
                        part=rel.source_part,
                    )
                )
                continue

            suffix = Path(target).suffix or ".bin"
            asset_id = f"img{image_index}"
            image_index += 1
            exported = assets_dir / f"{asset_id}{suffix}"
            with self.package.open_entry(target) as src, exported.open("wb") as dst:
                # 图片按流复制，避免把二进制整体放入最终 XML。
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)

            asset = {
                "id": asset_id,
                "type": "image",
                "source": "embedded",
                "file": str(exported.relative_to(self.output_dir)).replace("\\", "/"),
                "contentType": self._content_type_for_part(target),
                "sizeBytes": exported.stat().st_size,
                "relationshipId": rel.id,
                "sourcePart": rel.source_part,
                "packagePath": target,
            }
            assets.append(asset)
            lookup[(rel.source_part, rel.id)] = asset
        return assets, lookup

    def _content_type_for_part(self, part_name: str) -> str | None:
        """从 Content Types 中推断资源 MIME 类型。"""
        overrides = self.content_types["overrides"]
        defaults = self.content_types["defaults"]
        if part_name in overrides:
            return overrides[part_name]
        ext = Path(part_name).suffix.lstrip(".").lower()
        if ext in defaults:
            return defaults[ext]
        guessed, _ = mimetypes.guess_type(part_name)
        return guessed
