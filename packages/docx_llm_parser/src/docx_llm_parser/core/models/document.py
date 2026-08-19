"""Document-level parser models: options, styles, parse result, and OCR records."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

from ooxml_llm_core.models import ContentTypes, MetricsSnapshot, ParseWarning, RelationshipRecord

from ..enums import RevisionMode
from .blocks import AncillaryItem, Block
from .content import Chart, ImageAsset, RunFormat, SmartArt


class OcrResultRecord(TypedDict, total=False):
    status: Literal["success", "empty", "error"]
    text: str
    error_code: str
    error_message: str


OcrStoredResult = str | OcrResultRecord


class DocumentManifest(TypedDict):
    """Small document overview returned before rendering or resource extraction."""

    pages: int
    tables: int
    images: int
    footnotes: int
    endnotes: int
    comments: int


@dataclass(frozen=True)
class ParseOptions:
    """Parse configuration; immutable to keep concurrent tasks from interfering with each other."""

    preserve_empty_paragraphs: bool = False
    include_runs: bool = True
    include_raw_hints: bool = True
    debug: bool = False
    revision_mode: RevisionMode = RevisionMode.FINAL
    output_dir: Path = Path("out")
    max_zip_entries: int = 10000
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024
    ocr: object | None = None
    ocr_workers: int = 4
    ocr_timeout: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision_mode", RevisionMode.parse(self.revision_mode))
        limits = {
            "max_zip_entries": self.max_zip_entries,
            "max_entry_uncompressed_bytes": self.max_entry_uncompressed_bytes,
            "max_total_uncompressed_bytes": self.max_total_uncompressed_bytes,
        }
        for name, value in limits.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if isinstance(self.ocr_workers, bool) or not isinstance(self.ocr_workers, int) or self.ocr_workers <= 0:
            raise ValueError("ocr_workers must be greater than zero")
        if (
            isinstance(self.ocr_timeout, bool)
            or not isinstance(self.ocr_timeout, (int, float))
            or not math.isfinite(self.ocr_timeout)
            or self.ocr_timeout <= 0
        ):
            raise ValueError("ocr_timeout must be greater than zero")
        if self.ocr is not None and not any(
            callable(getattr(self.ocr, method, None)) for method in ("extract", "extract_result")
        ):
            raise TypeError("ocr must provide an extract(image_bytes) or extract_result(image_bytes) method")


@dataclass(slots=True)
class StyleRecord:
    """Word style summary."""

    style_id: str
    type: str = "unknown"
    name: str | None = None
    based_on: str | None = None
    next: str | None = None
    outline_level: int | None = None
    numbering_num_id: str | None = None
    numbering_level: int | None = None
    run_format: RunFormat = field(default_factory=dict)
    is_default: bool = False
    resolved_heading_level: int | None = None


@dataclass
class ParsedDocument:
    """Full internal parse result; the final output is further reduced."""

    metadata: dict[str, object]
    package_info: dict[str, object]
    blocks: list[Block]
    relationships: list[RelationshipRecord]
    styles: list[StyleRecord]
    warnings: list[ParseWarning]
    debug_dir: str | None = None
    content_types: ContentTypes = field(default_factory=lambda: ContentTypes(defaults={}, overrides={}))
    assets: list[ImageAsset] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    smartarts: list[SmartArt] = field(default_factory=list)
    headers: list[AncillaryItem] = field(default_factory=list)
    footers: list[AncillaryItem] = field(default_factory=list)
    footnotes: list[AncillaryItem] = field(default_factory=list)
    endnotes: list[AncillaryItem] = field(default_factory=list)
    comments: list[AncillaryItem] = field(default_factory=list)
    numbering: dict[str, object] = field(default_factory=dict)
    ocr_results: dict[str, OcrStoredResult] = field(default_factory=dict)
    metrics: MetricsSnapshot = field(default_factory=lambda: MetricsSnapshot(stagesMs={}, counters={}))

    def to_dict(self) -> dict[str, object]:
        return {
            "metadata": self.metadata,
            "packageInfo": self.package_info,
            "blocks": self.blocks,
            "relationships": [asdict(item) for item in self.relationships],
            "styles": [asdict(item) for item in self.styles],
            "warnings": [asdict(item) for item in self.warnings],
            "debugDir": self.debug_dir,
            "contentTypes": self.content_types,
            "assets": self.assets,
            "charts": self.charts,
            "smartarts": self.smartarts,
            "headers": self.headers,
            "footers": self.footers,
            "footnotes": self.footnotes,
            "endnotes": self.endnotes,
            "comments": self.comments,
            "numbering": self.numbering,
            "ocrResults": self.ocr_results,
            "metrics": self.metrics,
        }


__all__ = ["DocumentManifest", "OcrResultRecord", "OcrStoredResult", "ParseOptions", "ParsedDocument", "StyleRecord"]
