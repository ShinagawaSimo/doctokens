"""Shared Office container and reading data models.

Common container metadata and parser output contracts live here.
Format-specific models (paragraphs, runs, cells, slides, etc.) stay in
their respective parser packages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypedDict


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


Source = str | Path | bytes
