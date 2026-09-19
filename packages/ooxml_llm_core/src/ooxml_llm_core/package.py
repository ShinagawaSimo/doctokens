"""OPC ZIP package reader with security checks."""

from __future__ import annotations

import posixpath
import re
import zipfile
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import IO
from xml.etree import ElementTree as ET

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.models import ContentTypes, RelationshipRecord, ZipEntryInfo
from ooxml_llm_core.xml import NS, parse_xml, parse_xml_stream

# Minimum ratio of compressed/uncompressed size before an entry is
# flagged as suspicious.
_MIN_INFLATE_RATIO = 0.01
# Entries smaller than this (bytes) are exempt from ratio checks.
_GRACE_ENTRY_SIZE = 100_000
_PART_CACHE_ENTRY_BYTES = 512 * 1024
_PART_CACHE_TOTAL_BYTES = 8 * 1024 * 1024


class PackageError(RuntimeError):
    """OPC package structure or security check failed."""


class PackageReader:
    """On-demand OPC ZIP reader. Never extracts entries to disk."""

    def __init__(self, source: str | Path | bytes, limits: PackageLimits) -> None:
        self._source = source
        self.limits = limits
        self._zip: zipfile.ZipFile | None = None
        self._entry_index: list[ZipEntryInfo] | None = None
        self._names: set[str] = set()
        self._part_cache: dict[str, bytes] = {}
        self._part_cache_bytes = 0
        self._relationships_by_source: dict[str, tuple[RelationshipRecord, ...]] = {}
        self._all_relationships: tuple[RelationshipRecord, ...] | None = None

    def __enter__(self) -> PackageReader:
        try:
            source = BytesIO(self._source) if isinstance(self._source, bytes) else Path(self._source)
            self._zip = zipfile.ZipFile(source, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            if isinstance(self._source, bytes):
                raise PackageError("Not a valid zip byte stream") from exc
            raise PackageError(f"Not a zip file: {self._source}") from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        self._part_cache.clear()
        self._part_cache_bytes = 0
        self._relationships_by_source.clear()
        self._all_relationships = None

    @property
    def zip_file(self) -> zipfile.ZipFile:
        if self._zip is None:
            raise PackageError("PackageReader is not open")
        return self._zip

    def validate(self, required_part: str | None = None) -> None:
        """Check that required OPC parts exist.

        *required_part* is format-specific (e.g. ``"word/document.xml"``).
        When ``None`` only ``[Content_Types].xml`` is required.
        """
        index = self.read_entry_index()
        names = {item["name"] for item in index}
        if "[Content_Types].xml" not in names:
            raise PackageError("Missing [Content_Types].xml")
        if required_part is not None and required_part not in names:
            raise PackageError(f"Missing {required_part}")

    def exists(self, name: str) -> bool:
        self._ensure_index()
        return name in self._names

    def read_entry_index(self) -> list[ZipEntryInfo]:
        if self._entry_index is not None:
            return self._entry_index

        zip_entries = self.zip_file.infolist()
        if len(zip_entries) > self.limits.max_zip_entries:
            raise PackageError(f"Too many zip entries: {len(zip_entries)}")

        total_uncompressed = 0
        entry_index: list[ZipEntryInfo] = []
        names: set[str] = set()
        seen_lower: set[str] = set()
        for zip_entry in zip_entries:
            name = zip_entry.filename.replace("\\", "/")
            self._validate_entry_name(name)

            if zip_entry.flag_bits & 0x1:
                raise PackageError(f"Encrypted entry is not supported: {name}")

            lower_name = name.lower()
            if lower_name in seen_lower:
                raise PackageError(f"Duplicate zip entry: {name}")
            if not name:
                raise PackageError("Zip entry with empty name")
            seen_lower.add(lower_name)

            if zip_entry.file_size > self.limits.max_entry_uncompressed_bytes:
                raise PackageError(f"Entry too large: {name} ({zip_entry.file_size} bytes)")
            total_uncompressed += zip_entry.file_size
            if total_uncompressed > self.limits.max_total_uncompressed_bytes:
                raise PackageError(f"Package uncompressed size too large: {total_uncompressed} bytes")

            if zip_entry.file_size > _GRACE_ENTRY_SIZE and zip_entry.compress_size > 0:
                compression_ratio = zip_entry.compress_size / zip_entry.file_size
                if compression_ratio < _MIN_INFLATE_RATIO:
                    raise PackageError(
                        f"Suspicious compression ratio for {name}: {zip_entry.compress_size}/{zip_entry.file_size}"
                    )

            names.add(name)
            entry_index.append(
                {
                    "name": name,
                    "compressedSize": zip_entry.compress_size,
                    "uncompressedSize": zip_entry.file_size,
                    "crc": zip_entry.CRC,
                }
            )

        self._entry_index = entry_index
        self._names = names
        return entry_index

    def read_content_types(self) -> ContentTypes:
        root = self.read_xml("[Content_Types].xml")

        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}
        for child in root:
            if child.tag == f"{{{NS['ct']}}}Default":
                defaults[child.attrib["Extension"]] = child.attrib["ContentType"]
            elif child.tag == f"{{{NS['ct']}}}Override":
                part_name = child.attrib["PartName"].lstrip("/")
                overrides[part_name] = child.attrib["ContentType"]
        return {"defaults": defaults, "overrides": overrides}

    def read_all_relationships(self) -> list[RelationshipRecord]:
        if self._all_relationships is not None:
            return list(self._all_relationships)
        self._ensure_index()
        rels_paths = sorted(
            name for name in self._names if name == "_rels/.rels" or ("/_rels/" in name and name.endswith(".rels"))
        )
        relationships: list[RelationshipRecord] = []
        for rels_path in rels_paths:
            source_part = source_part_from_rels_path(rels_path)
            relationships.extend(self.read_relationships_for_part(source_part))
        self._all_relationships = tuple(relationships)
        return relationships

    def read_relationships_for_part(self, source_part: str | None) -> list[RelationshipRecord]:
        source = source_part or ""
        cached = self._relationships_by_source.get(source)
        if cached is not None:
            return list(cached)
        rels_path = rels_path_for_part(source_part)
        if not self.exists(rels_path):
            self._relationships_by_source[source] = ()
            return []

        root = self.read_xml(rels_path)

        records: list[RelationshipRecord] = []
        for rel in root:
            if rel.tag != f"{{{NS['rel']}}}Relationship":
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
        self._relationships_by_source[source] = tuple(records)
        return records

    def read_part(self, name: str) -> bytes:
        """Read a small package part, caching bounded immutable bytes per session."""
        normalized = self._normalized_name(name)
        cached = self._part_cache.get(normalized)
        if cached is not None:
            return cached
        with self.open_entry(normalized) as stream:
            data = stream.read()
        if len(data) <= _PART_CACHE_ENTRY_BYTES and self._part_cache_bytes + len(data) <= _PART_CACHE_TOTAL_BYTES:
            self._part_cache[normalized] = data
            self._part_cache_bytes += len(data)
        return data

    def read_xml(self, name: str) -> ET.Element:
        """Parse one package XML part from the bounded bytes cache when eligible."""
        normalized = self._normalized_name(name)
        self._ensure_index()
        if normalized not in self._names:
            raise PackageError(f"Missing zip entry: {normalized}")
        if self.zip_file.getinfo(normalized).file_size > _PART_CACHE_ENTRY_BYTES:
            with self.open_entry(normalized) as stream:
                return parse_xml_stream(stream)
        return parse_xml(self.read_part(normalized))

    def open_entry(self, name: str) -> IO[bytes]:
        self._ensure_index()
        normalized = self._normalized_name(name)
        if normalized not in self._names:
            raise PackageError(f"Missing zip entry: {normalized}")
        return self.zip_file.open(normalized, "r")

    @staticmethod
    def _normalized_name(name: str) -> str:
        return name.replace("\\", "/")

    def _ensure_index(self) -> None:
        if self._entry_index is None:
            self.read_entry_index()

    @staticmethod
    def _validate_entry_name(name: str) -> None:
        if name.startswith("/") or name.startswith("\\"):
            raise PackageError(f"Unsafe absolute zip entry path: {name}")
        if re.match(r"^[A-Za-z]:", name):
            raise PackageError(f"Unsafe drive zip entry path: {name}")
        parts = [part for part in name.replace("\\", "/").split("/") if part]
        if ".." in parts:
            raise PackageError(f"Unsafe parent traversal zip entry path: {name}")


def rels_path_for_part(source_part: str | None) -> str:
    if not source_part:
        return "_rels/.rels"
    source = source_part.replace("\\", "/").lstrip("/")
    parent = posixpath.dirname(source)
    base = posixpath.basename(source)
    if parent:
        return f"{parent}/_rels/{base}.rels"
    return f"_rels/{base}.rels"


def source_part_from_rels_path(rels_path: str) -> str | None:
    rels = rels_path.replace("\\", "/")
    if rels == "_rels/.rels":
        return None
    marker = "/_rels/"
    if marker not in rels or not rels.endswith(".rels"):
        return None
    parent, rel_file = rels.split(marker, 1)
    source_file = rel_file[: -len(".rels")]
    return f"{parent}/{source_file}" if parent else source_file


def resolve_relationship_target(source_part: str, target: str, target_mode: str | None) -> str | None:
    if target_mode == "External":
        return target
    normalized = target.replace("\\", "/")
    if normalized.startswith("/"):
        return posixpath.normpath(normalized.lstrip("/"))
    base = posixpath.dirname(source_part) if source_part else ""
    return posixpath.normpath(posixpath.join(base, normalized))
