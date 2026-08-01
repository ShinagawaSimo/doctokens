"""提取 DOCX 中可供 LLM 引用的媒体资源。

图片以内容哈希命名防冲突，下游工具通过文件路径直接读取。
超大图片自动压缩以控制 base64 token 消耗。
"""

from __future__ import annotations

import hashlib
import mimetypes
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..core.models import AssetLookup, ContentTypes, ImageAsset, ParseWarning
from ..core.package import PackageReader
from ..core.relationships import RelationshipIndex

IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

# 图片压缩阈值：超过此大小（字节）的图片在导出时自动压缩。
# 1MB base64 后约 133 万字符、约 33 万 token，对 LLM 来说非常昂贵。
_MAX_IMAGE_BYTES = 1_000_000  # 1 MB
_MAX_IMAGE_PX = 2000  # 压缩时缩放到此最大像素尺寸
_JPEG_QUALITY = 85  # JPEG 压缩质量


class AssetExtractor:
    """从 relationships 中识别图片，并按需导出到 assets 目录。"""

    def __init__(
        self,
        package: PackageReader,
        relationships: RelationshipIndex,
        content_types: ContentTypes,
        output_dir: Path,
        warnings: list[ParseWarning],
    ) -> None:
        self.package = package
        self.relationships = relationships
        self.content_types = content_types
        self.output_dir = output_dir
        self.warnings = warnings

    def extract(self) -> tuple[list[ImageAsset], AssetLookup]:
        """导出图片资源，并返回 relationship 到 asset 的索引。"""
        assets_dir = self.output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        assets: list[ImageAsset] = []
        lookup: AssetLookup = {}
        image_index = 1
        for rel in self.relationships.by_type(IMAGE_REL_TYPE):
            if rel.target_mode == "External":
                asset: ImageAsset = {
                    "id": f"img{image_index}",
                    "type": "image",
                    "source": "external",
                    "href": rel.target,
                }
                image_index += 1
                assets.append(asset)
                lookup[(rel.source_part, rel.id)] = asset
                continue

            target = rel.resolved_target
            if not target or not self.package.exists(target):
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
            with self.package.open_entry(target) as src:
                data = src.read()
            file_hash = hashlib.sha256(data).hexdigest()[:8]

            # 超大图片压缩以控制下游 base64 token 消耗
            if len(data) > _MAX_IMAGE_BYTES:
                compressed = self._compress_image(data)
                if compressed is not None:
                    data = compressed
                    suffix = ".jpg"

            exported = assets_dir / f"{asset_id}_{file_hash}{suffix}"
            exported.write_bytes(data)

            asset = {
                "id": asset_id,
                "type": "image",
                "source": "embedded",
                "file": str(exported.relative_to(self.output_dir)).replace("\\", "/"),
            }
            content_type = self._content_type_for_part(target)
            if content_type is not None:
                asset["contentType"] = content_type
            assets.append(asset)
            lookup[(rel.source_part, rel.id)] = asset
        return assets, lookup

    def _compress_image(self, data: bytes) -> bytes | None:
        """尝试压缩图片数据。失败时返回 None，调用方保留原始数据。"""
        try:
            with Image.open(BytesIO(data)) as source_image:
                img: Image.Image = source_image.copy()
            # 缩放到最大像素尺寸
            w, h = img.size
            if max(w, h) > _MAX_IMAGE_PX:
                ratio = _MAX_IMAGE_PX / max(w, h)
                img = img.resize(
                    (int(w * ratio), int(h * ratio)),
                    Image.Resampling.LANCZOS,
                )
            # RGBA 转 RGB（JPEG 不支持透明通道）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
            return buf.getvalue()
        except Exception:
            self.warnings.append(
                ParseWarning(
                    level="warning",
                    code="IMAGE_COMPRESS_FAILED",
                    message="Image compression failed, keeping original",
                )
            )
            return None

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
