"""Structural DOCX model types: body blocks and ancillary content."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from .content import ContentControl, ParagraphBorders, RawHint, Run


class NumberingLabel(TypedDict):
    numId: str
    level: int
    label: str
    text: str
    format: str
    template: str | None
    suffix: str
    counter: int
    markerFormat: dict[str, bool | str | None]
    markerFont: NotRequired[str]
    pictureBulletId: str | None
    markerImageId: str | None
    legal: bool


class ParagraphBlockRequired(TypedDict):
    id: str
    type: Literal["paragraph"]
    part: str
    order: int
    page: int
    styleId: str | None
    text: str


class ParagraphBlock(ParagraphBlockRequired, total=False):
    alignment: str
    borders: ParagraphBorders
    runs: list[Run]
    rawHints: list[RawHint]
    numbering: NumberingLabel
    anchors: list[str]
    section: int
    contentControls: list[ContentControl]


class HeadingBlockRequired(TypedDict):
    id: str
    type: Literal["heading"]
    part: str
    order: int
    page: int
    styleId: str | None
    text: str
    level: int
    headingSource: Literal["style"]


class HeadingBlock(HeadingBlockRequired, total=False):
    alignment: str
    borders: ParagraphBorders
    runs: list[Run]
    rawHints: list[RawHint]
    numbering: NumberingLabel
    anchors: list[str]
    section: int
    contentControls: list[ContentControl]


TextBlock = ParagraphBlock | HeadingBlock


class TableCellRequired(TypedDict):
    rowIndex: int
    colIndex: int
    rowSpan: int
    colSpan: int
    text: str
    blocks: list[Block]


class TableCell(TableCellRequired, total=False):
    vMerge: str


class TableRowRequired(TypedDict):
    rowIndex: int
    cells: list[TableCell]


class TableRow(TableRowRequired, total=False):
    isHeader: bool


class TableBlockRequired(TypedDict):
    id: str
    type: Literal["table"]
    part: str
    order: int
    page: int
    tableId: str
    segmentIndex: int
    rows: list[TableRow]
    columnCount: int
    section: int


class TableBlock(TableBlockRequired, total=False):
    contentControls: list[ContentControl]


Block = TextBlock | TableBlock


class BodyEventRequired(TypedDict):
    id: str
    type: str
    order: int
    part: str


class BodyEvent(BodyEventRequired, total=False):
    textPreview: str
    numberingLabel: str
    level: int
    rowCount: int
    columnCount: int


class AncillaryContent(TypedDict):
    text: str
    runs: list[Run]
    rawHints: list[RawHint]


class AncillaryItemRequired(TypedDict):
    id: str | None
    loc: str
    text: str
    runs: list[Run]


class AncillaryItem(AncillaryItemRequired, total=False):
    rawHints: list[RawHint]
    author: str | None
    date: str | None
    anchor: str
    parentId: str
    resolved: bool


class AncillaryResult(TypedDict):
    headers: list[AncillaryItem]
    footers: list[AncillaryItem]
    footnotes: list[AncillaryItem]
    endnotes: list[AncillaryItem]
    comments: list[AncillaryItem]


InlineContainer = TextBlock | AncillaryItem


__all__ = [
    "AncillaryContent",
    "AncillaryItem",
    "AncillaryResult",
    "Block",
    "BodyEvent",
    "HeadingBlock",
    "InlineContainer",
    "NumberingLabel",
    "ParagraphBlock",
    "TableBlock",
    "TableBlockRequired",
    "TableCell",
    "TableRow",
    "TextBlock",
]
