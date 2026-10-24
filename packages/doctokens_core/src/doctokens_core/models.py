"""Shared OPC-level data models.

Models that apply to ALL OOXML format parsers live here.
Format-specific models (paragraphs, runs, cells, slides, etc.) stay in
their respective parser packages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, TypedDict


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


ResourceSource = Literal["embedded", "external"]


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    """Stable metadata for a resource exposed by a parsed package."""

    id: str
    kind: str
    source: ResourceSource
    locator: str
    content_type: str | None = None
    part: str | None = None
    external_target: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


Density = Literal["plain", "structural", "semantic"]


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Public result for one parse or render operation."""

    text: str
    density: Density
    selection: dict[str, object]
    report: ParseReport
    resources: tuple[ResourceDescriptor, ...] = ()
    syntax_version: str = "legacy-markup/0"
    media_type: str = "text/plain"

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "density": self.density,
            "selection": self.selection,
            "report": self.report.to_dict(),
            "resources": [item.to_dict() for item in self.resources],
            "syntax_version": self.syntax_version,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class ParseReport:
    """Stable parser-facing diagnostics and orientation report."""

    format: str
    schema_version: int
    manifest: dict[str, object]
    warnings: tuple[ParseWarning, ...]
    metrics: MetricsSnapshot

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "schemaVersion": self.schema_version,
            "manifest": self.manifest,
            "warnings": [{"code": item.code, "message": item.message, "locator": item.locator} for item in self.warnings],
            "metrics": self.metrics,
        }


MetricValue = int | float | str
JsonObject = dict[str, "JsonObject | MetricValue"]


class MetricsSnapshot(TypedDict, total=False):
    """Parser/render timing and counter snapshot."""

    totalMs: float
    parseTotalMs: float
    stagesMs: dict[str, float]
    counters: dict[str, MetricValue]
