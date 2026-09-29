"""XLSX parser intermediate models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from ooxml_llm_core.annotations import AnnotationMention, ThreadedAnnotation
from ooxml_llm_core.models import ParseReport
from ooxml_llm_core.options import PackageOptions


@dataclass(frozen=True)
class ParseOptions(PackageOptions):
    """XLSX parser options sharing OPC limits and diagnostics with other formats."""

    locale: str = "zh-CN"

    def __post_init__(self) -> None:
        self.validate_package_options()
        if not isinstance(self.locale, str) or not self.locale.strip():
            raise ValueError("locale must be a non-empty string")


class RichTextRun(TypedDict, total=False):
    text: str
    bold: bool
    italic: bool
    underline: bool
    color: str


class ThreadedComment(ThreadedAnnotation, total=False):
    """A modern cell comment, with its conversation linkage resolved locally."""

    mentions: list[AnnotationMention]


class Cell(TypedDict, total=False):
    """A single spreadsheet cell in typed IR."""

    ref: str  # A1-style reference, e.g. "A1"
    row: int  # 1-based row number
    col: int  # 1-based column number
    text: str  # resolved display text
    raw: str  # reconstructed formula-bar content for a non-formula cell
    numberFormatColor: str  # selected format-section color overrides font color
    type: str  # "number", "string", "boolean", "error", "date"
    formula: str  # formula text from <f> element (e.g. "SUM(A1:A10)")
    si: str  # shared formula index for slave cells
    shared_ref: str  # shared formula range (master cell only)
    formulaType: str  # "array" | "dataTable"
    formulaRange: str  # array/dataTable range from <f ref=...>
    colspan: int  # merge: column span for anchor cell
    rowspan: int  # merge: row span for anchor cell
    shadow: bool  # merge: true for cells covered by a merge anchor
    spillRange: str  # dynamic array: A1-style spill range on the anchor cell
    spillFrom: str  # dynamic array: A1 ref of the source cell on spill recipients
    dynamicArray: bool  # true when the formula carries the dynamic-array aca marker
    hidden: bool  # row hidden state
    outlineLevel: int  # row outline level (0 = none)
    collapsed: bool  # row collapsed state
    hyperlink: str  # resolved URL or internal ref from <hyperlink> + rels
    comment: str  # comment text from legacy or threaded comment
    commentAuthor: str  # author name for the comment
    threadedComments: list[ThreadedComment]  # modern comments and replies on this cell
    style: int  # index into cellXfs for style lookup
    rich: list[RichTextRun]  # formatted text runs [{text, bold, italic, color}]
    richValue: RichCellValue  # modern entity/image value resolved from richData
    cellControl: CellControl  # interactive cell control (currently checkbox)


class RichCellValue(TypedDict, total=False):
    """LLM-facing projection of an Excel rich value.

    Raw richData indices and relationship IDs are intentionally omitted.  A
    descriptor keeps only the fallback/display information and safe resource
    locator needed to understand the cell without refreshing external data.
    """

    type: str
    display: str
    fallback: str
    fields: dict[str, str]
    imagePart: str
    imageUrl: str
    alt: str
    sizing: int
    width: str
    height: str
    computed: bool
    decorative: bool
    warning: str


class CellControl(TypedDict, total=False):
    kind: str
    default: int
    value: str
    state: str


class TableInfo(TypedDict, total=False):
    """Excel Table (ListObject) metadata."""

    id: str  # deterministic table id
    name: str  # displayName from the table definition
    ref: str  # A1 range e.g. "A5:K250001"
    columns: list[str]  # declared column names
    totalsRow: bool  # True when totals row is shown


FilterColumn = TypedDict(
    "FilterColumn",
    {
        "col": int,
        "type": str,
        "values": list[str],
        "blank": bool,
        "calendarType": str,
        "operator": str,
        "value": str,
        "value2": str,
        "and": bool,
        "top": bool,
        "percent": bool,
        "rank": str,
        "filterValue": str,
        "dxfId": int,
        "cellColor": bool,
        "iconSet": str,
        "iconId": int,
        "dateGroup": list[dict[str, str]],
    },
    total=False,
)


class DataValidation(TypedDict, total=False):
    ranges: str
    type: str
    formula1: str
    allowBlank: bool


class ConditionalFormat(TypedDict, total=False):
    ranges: str
    priority: int
    ruleType: str
    formulas: list[str]
    dxfId: int
    stopIfTrue: bool
    operator: str
    text: str
    rank: int
    percent: bool
    formatKind: str
    formatDetails: dict[str, object]
    dxfStyle: str


class DrawingImage(TypedDict, total=False):
    id: str
    ref: str
    alt: str
    part: str


class ChartPoint(TypedDict, total=False):
    category: str
    value: str
    x: str
    y: str
    bubbleSize: str


class DrawingChartSeries(TypedDict, total=False):
    index: int
    pointCount: int
    name: str
    min: float
    max: float
    points: list[ChartPoint]
    plotIndex: int
    chartType: str
    xValues: list[str]
    yValues: list[str]
    bubbleSizes: list[str]
    hidden: bool


class DrawingChart(TypedDict, total=False):
    id: str
    ref: str
    type: str
    title: str
    series_count: int
    part: str
    series: list[DrawingChartSeries]
    plotTypes: list[str]


class PivotTableInfo(TypedDict, total=False):
    id: str
    ref: str
    name: str
    cacheId: int
    sourceRef: str
    sourceSheet: str
    rowFields: list[str]
    columnFields: list[str]
    pageFields: list[str]
    dataFields: list[str]
    filters: list[str]
    fieldNames: list[str]
    style: str


class PivotCacheInfo(TypedDict, total=False):
    id: str
    cacheId: int
    sourceRef: str
    sourceSheet: str
    fields: list[str]
    refreshOnLoad: bool
    recordCount: int
    slicerData: bool
    timelineData: bool


class SlicerInfo(TypedDict, total=False):
    id: str
    name: str
    sourceName: str
    cacheId: int
    type: str


class TimelineInfo(TypedDict, total=False):
    id: str
    name: str
    sourceName: str
    cacheId: int
    level: str


class DefinedName(TypedDict):
    name: str
    ref: str
    scopeSheet: str | None
    hidden: bool


class WorkbookMetadata(TypedDict, total=False):
    source: str
    defined_names: list[DefinedName]
    external_links: list[str]
    pivot_caches: list[PivotCacheInfo]
    slicers: list[SlicerInfo]
    timelines: list[TimelineInfo]


class SheetInfo(TypedDict, total=False):
    """Sheet metadata and cell grid."""

    name: str
    part: str
    kind: str  # "worksheet" | "chartsheet"
    rows: list[list[Cell]]
    state: str  # "visible" | "hidden" | "veryHidden"
    hidden_cols: list[tuple[int, int]]  # (min_col, max_col) ranges from <cols>
    sheet_protection: bool  # True when <sheetProtection> is present
    tables: list[TableInfo]  # [{id, name, ref, columns, totalsRow}]
    filter_range: str  # A1 range from <autoFilter> (structural only)
    filter_cols: list[FilterColumn]  # Structured autoFilter column rules.
    data_validations: list[DataValidation]  # [{ranges, type, formula1, allowBlank}]
    conditional_formats: list[ConditionalFormat]  # Rule conditions plus visual-format semantics.
    images: list[DrawingImage]  # [{id, ref, alt}] from drawing anchors
    charts: list[DrawingChart]  # [{id, ref, type, title, series_count}]
    pivot_tables: list[PivotTableInfo]  # [{id, ref, name}] detected pivot tables


class ParsedWorkbook(TypedDict):
    """Parsed XLSX workbook IR."""

    sheets: list[SheetInfo]
    metadata: WorkbookMetadata
    fmt_index: object  # FormatIndex from formats.py
    report: ParseReport
