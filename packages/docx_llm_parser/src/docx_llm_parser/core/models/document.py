"""Document-level parser models: options, styles, parse result, and OCR records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, TypedDict

from ooxml_llm_core.models import ContentTypes, MetricsSnapshot, ParseReport, ParseWarning, RelationshipRecord
from ooxml_llm_core.options import PackageOptions

from ..enums import RevisionMode
from .blocks import AncillaryItem, Block
from .content import Chart, ImageAsset, ParagraphBorders, RunFormat, SmartArt


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
class ParseOptions(PackageOptions):
    """Parse configuration; immutable to keep concurrent tasks from interfering with each other."""

    preserve_empty_paragraphs: bool = False
    include_runs: bool = True
    include_raw_hints: bool = True
    revision_mode: RevisionMode = RevisionMode.FINAL
    ocr: object | None = None
    ocr_workers: int = 4
    ocr_timeout: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision_mode", RevisionMode.parse(self.revision_mode))
        self.validate_package_options()
        self.validate_ocr_options(self.ocr, self.ocr_workers, self.ocr_timeout)


@dataclass(slots=True)
class StyleRecord:
    """Word style summary."""

    style_id: str
    type: str = "unknown"
    name: str | None = None
    based_on: str | None = None
    link: str | None = None
    next: str | None = None
    alignment: str | None = None
    borders: ParagraphBorders = field(default_factory=dict)
    outline_level: int | None = None
    numbering_num_id: str | None = None
    numbering_level: int | None = None
    run_format: RunFormat = field(default_factory=dict)
    is_custom: bool = False
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
    content_types: ContentTypes = field(default_factory=lambda: ContentTypes(defaults={}, overrides={}))
    assets: list[ImageAsset] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    smartarts: list[SmartArt] = field(default_factory=list)
    headers: list[AncillaryItem] = field(default_factory=list)
    footers: list[AncillaryItem] = field(default_factory=list)
    footnotes: list[AncillaryItem] = field(default_factory=list)
    endnotes: list[AncillaryItem] = field(default_factory=list)
    comments: list[AncillaryItem] = field(default_factory=list)
    ocr_results: dict[str, OcrStoredResult] = field(default_factory=dict)
    metrics: MetricsSnapshot = field(default_factory=lambda: MetricsSnapshot(stagesMs={}, counters={}))
    report: ParseReport | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "metadata": self.metadata,
            "packageInfo": self.package_info,
            "blocks": self.blocks,
            "relationships": [asdict(item) for item in self.relationships],
            "styles": [asdict(item) for item in self.styles],
            "warnings": [asdict(item) for item in self.warnings],
            "contentTypes": self.content_types,
            "assets": self.assets,
            "charts": self.charts,
            "smartarts": self.smartarts,
            "headers": self.headers,
            "footers": self.footers,
            "footnotes": self.footnotes,
            "endnotes": self.endnotes,
            "comments": self.comments,
            "ocrResults": self.ocr_results,
            "metrics": self.metrics,
            "report": self.report.to_dict() if self.report is not None else None,
        }


__all__ = ["DocumentManifest", "OcrResultRecord", "OcrStoredResult", "ParseOptions", "ParsedDocument", "StyleRecord"]
