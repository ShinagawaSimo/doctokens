"""读取 DOCX 的 ZIP 包、Content Types 和 Relationships。"""

from __future__ import annotations

import posixpath
import re
import zipfile
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import IO
from xml.etree import ElementTree as ET

from .constants import NS
from .models import ContentTypes, ParseOptions, RelationshipRecord, ZipEntryInfo

# 压缩比下限：解压后大小 / 压缩后大小的比值若低于此值，视为可疑压缩包。
_MIN_INFLATE_RATIO = 0.01
# 小 entry 豁免阈值（字节）：小于此值的 entry 不做压缩比检查。
_GRACE_ENTRY_SIZE = 100_000


class DocxPackageError(RuntimeError):
    """DOCX 包结构或安全校验失败。"""

    pass


class PackageReader:
    """按需读取 DOCX 包，不把所有 entry 解压到磁盘。"""

    def __init__(self, source: Path | bytes, options: ParseOptions) -> None:
        self._source = source
        self.options = options
        self._zip: zipfile.ZipFile | None = None
        self._entry_index: list[ZipEntryInfo] | None = None
        self._names: set[str] = set()

    def __enter__(self) -> PackageReader:
        """打开 zip 文件，并确认输入至少是可读 ZIP。"""
        if isinstance(self._source, bytes):
            if not zipfile.is_zipfile(BytesIO(self._source)):
                raise DocxPackageError("Not a valid zip/docx byte stream")
            self._zip = zipfile.ZipFile(BytesIO(self._source), "r")
        else:
            path = Path(self._source)
            if not zipfile.is_zipfile(path):
                raise DocxPackageError(f"Not a zip/docx file: {path}")
            self._zip = zipfile.ZipFile(path, "r")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._zip is not None:
            self._zip.close()

    @property
    def zip_file(self) -> zipfile.ZipFile:
        """返回当前打开的 zip handle。"""
        if self._zip is None:
            raise DocxPackageError("PackageReader is not open")
        return self._zip

    def validate(self) -> None:
        """校验 DOCX 必要 entry 和安全阈值。"""
        index = self.read_entry_index()
        names = {item["name"] for item in index}
        if "[Content_Types].xml" not in names:
            # OPC 包必须包含 Content Types。
            raise DocxPackageError("Missing [Content_Types].xml")
        if "word/document.xml" not in names:
            # MVP 只解析 Word 主文档，没有正文 part 就无法继续。
            raise DocxPackageError("Missing word/document.xml")

    def exists(self, name: str) -> bool:
        """检查 entry 是否存在。"""
        self._ensure_index()
        return name in self._names

    def read_entry_index(self) -> list[ZipEntryInfo]:
        """建立 ZIP entry 索引，并做大小和路径安全检查。"""
        if self._entry_index is not None:
            # 索引只构建一次，后续复用只读结果。
            return self._entry_index

        infos = self.zip_file.infolist()
        if len(infos) > self.options.max_zip_entries:
            # entry 过多可能是异常文档或压缩包攻击。
            raise DocxPackageError(f"Too many zip entries: {len(infos)}")

        total_uncompressed = 0
        rows: list[ZipEntryInfo] = []
        names: set[str] = set()
        seen_lower: set[str] = set()
        for info in infos:
            name = info.filename.replace("\\", "/")
            self._validate_entry_name(name)

            # 加密 entry 拒绝。
            if info.flag_bits & 0x1:
                raise DocxPackageError(f"Encrypted entry is not supported: {name}")

            # 重复 entry 拒绝（大小写不敏感，参考 Apache POI）。
            lower_name = name.lower()
            if lower_name in seen_lower:
                raise DocxPackageError(f"Duplicate zip entry: {name}")
            if not name:
                raise DocxPackageError("Zip entry with empty name")
            seen_lower.add(lower_name)

            if info.file_size > self.options.max_entry_uncompressed_bytes:
                # 单 entry 太大时直接拒绝，防止内存被 XML 拉爆。
                raise DocxPackageError(f"Entry too large: {name} ({info.file_size} bytes)")
            total_uncompressed += info.file_size
            if total_uncompressed > self.options.max_total_uncompressed_bytes:
                # 总解压体积限制用于防 ZIP 炸弹。
                raise DocxPackageError(
                    f"Package uncompressed size too large: {total_uncompressed} bytes"
                )

            # 压缩比检查：小文件豁免，避免误判。
            if info.file_size > _GRACE_ENTRY_SIZE and info.compress_size > 0:
                ratio = info.compress_size / info.file_size
                if ratio < _MIN_INFLATE_RATIO:
                    raise DocxPackageError(
                        f"Suspicious compression ratio for {name}: "
                        f"{info.compress_size}/{info.file_size}"
                    )

            names.add(name)
            rows.append(
                {
                    "name": name,
                    "compressedSize": info.compress_size,
                    "uncompressedSize": info.file_size,
                    "crc": info.CRC,
                }
            )

        self._entry_index = rows
        self._names = names
        return rows

    def read_content_types(self) -> ContentTypes:
        """解析 [Content_Types].xml 中的默认类型和覆盖类型。"""
        with self.open_entry("[Content_Types].xml") as stream:
            root = ET.parse(stream).getroot()

        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}
        for child in root:
            if child.tag == f"{{{NS['ct']}}}Default":
                # Default 根据扩展名匹配 content type。
                defaults[child.attrib["Extension"]] = child.attrib["ContentType"]
            elif child.tag == f"{{{NS['ct']}}}Override":
                # Override 精确指定某个 part 的 content type。
                part_name = child.attrib["PartName"].lstrip("/")
                overrides[part_name] = child.attrib["ContentType"]
        return {"defaults": defaults, "overrides": overrides}

    def read_all_relationships(self) -> list[RelationshipRecord]:
        """读取包内所有 .rels 文件，构建完整 relationship 列表。"""
        self._ensure_index()
        rels_paths = sorted(
            name
            for name in self._names
            if name == "_rels/.rels" or ("/_rels/" in name and name.endswith(".rels"))
        )
        relationships: list[RelationshipRecord] = []
        for rels_path in rels_paths:
            # 根据 rels 文件路径反推出它所属的 source part。
            source_part = source_part_from_rels_path(rels_path)
            relationships.extend(self.read_relationships_for_part(source_part))
        return relationships

    def read_relationships_for_part(self, source_part: str | None) -> list[RelationshipRecord]:
        """读取指定 part 的 relationship 文件。"""
        rels_path = rels_path_for_part(source_part)
        if not self.exists(rels_path):
            # 很多 part 没有关系文件，这是正常情况。
            return []

        with self.open_entry(rels_path) as stream:
            root = ET.parse(stream).getroot()

        records: list[RelationshipRecord] = []
        source = source_part or ""
        for rel in root:
            if rel.tag != f"{{{NS['rel']}}}Relationship":
                # 只接受 OPC relationship 元素。
                continue
            rel_id = rel.attrib["Id"]
            rel_type = rel.attrib["Type"]
            target = rel.attrib["Target"]
            target_mode = rel.get("TargetMode")
            resolved = resolve_relationship_target(source, target, target_mode)
            records.append(
                RelationshipRecord(
                    source_part=source,
                    id=rel_id,
                    type=rel_type,
                    target=target,
                    target_mode=target_mode,
                    resolved_target=resolved,
                )
            )
        return records

    def open_entry(self, name: str) -> IO[bytes]:
        """按需打开 ZIP entry 的二进制流。"""
        self._ensure_index()
        normalized = name.replace("\\", "/")
        if normalized not in self._names:
            raise DocxPackageError(f"Missing zip entry: {normalized}")
        return self.zip_file.open(normalized, "r")

    def _ensure_index(self) -> None:
        """确保 ZIP 索引已构建。"""
        if self._entry_index is None:
            self.read_entry_index()

    @staticmethod
    def _validate_entry_name(name: str) -> None:
        """拒绝可能造成路径穿越或绝对路径写入的 entry 名称。"""
        if name.startswith("/") or name.startswith("\\"):
            raise DocxPackageError(f"Unsafe absolute zip entry path: {name}")
        if re.match(r"^[A-Za-z]:", name):
            raise DocxPackageError(f"Unsafe drive zip entry path: {name}")
        parts = [part for part in name.replace("\\", "/").split("/") if part]
        if ".." in parts:
            raise DocxPackageError(f"Unsafe parent traversal zip entry path: {name}")


def rels_path_for_part(source_part: str | None) -> str:
    """由 source part 路径计算对应 .rels 路径。"""
    if not source_part:
        # 根包关系固定在 _rels/.rels。
        return "_rels/.rels"
    source = source_part.replace("\\", "/").lstrip("/")
    parent = posixpath.dirname(source)
    base = posixpath.basename(source)
    if parent:
        return f"{parent}/_rels/{base}.rels"
    return f"_rels/{base}.rels"


def source_part_from_rels_path(rels_path: str) -> str | None:
    """由 .rels 路径反推出它描述的 source part。"""
    rels = rels_path.replace("\\", "/")
    if rels == "_rels/.rels":
        # 根包关系没有 source part。
        return None
    marker = "/_rels/"
    if marker not in rels or not rels.endswith(".rels"):
        return None
    parent, rel_file = rels.split(marker, 1)
    source_file = rel_file[: -len(".rels")]
    return f"{parent}/{source_file}" if parent else source_file


def resolve_relationship_target(
    source_part: str, target: str, target_mode: str | None
) -> str | None:
    """把 relationship target 解析为包内规范路径。"""
    if target_mode == "External":
        # 外部链接只记录，绝不在解析阶段访问网络。
        return target
    normalized = target.replace("\\", "/")
    if normalized.startswith("/"):
        # 绝对 target 是包根路径。
        return posixpath.normpath(normalized.lstrip("/"))
    base = posixpath.dirname(source_part) if source_part else ""
    # 相对 target 基于 source part 所在目录解析。
    return posixpath.normpath(posixpath.join(base, normalized))
