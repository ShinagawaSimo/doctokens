"""Shared OPC-level data models.

Models that apply to ALL OOXML format parsers live here.
Format-specific models (paragraphs, runs, cells, slides, etc.) stay in
their respective parser packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class ParseWarning:
    """Non-fatal issue encountered during parsing."""

    code: str
    message: str
    locator: str | None = None


class MetricsSnapshot(TypedDict):
    """A single point-in-time metrics reading."""

    stage: str
    elapsed_ms: float


MetricValue = int | float | str
JsonObject = dict[str, "JsonObject | MetricValue"]
