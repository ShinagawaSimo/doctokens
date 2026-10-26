"""OPC-specific package metadata, separate from reading result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class ZipEntryInfo(TypedDict):
    """Metadata for a single ZIP entry in an OPC package."""

    name: str
    compressedSize: int
    uncompressedSize: int
    crc: int


class ContentTypes(TypedDict):
    """Parsed [Content_Types].xml result."""

    defaults: dict[str, str]
    overrides: dict[str, str]


@dataclass(frozen=True, order=True)
class RelationshipRecord:
    """A single OPC relationship record.

    ``resolved_target`` is the canonical path within the package
    (relative to root), or the original URL for External targets.
    """

    source_part: str
    id: str
    type: str
    target: str
    target_mode: str | None = None
    resolved_target: str | None = None
