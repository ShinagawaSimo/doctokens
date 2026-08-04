"""XLSX parser intermediate models."""

from __future__ import annotations

from typing import TypedDict


class Cell(TypedDict, total=False):
    """A single spreadsheet cell in typed IR."""

    ref: str          # A1-style reference, e.g. "A1"
    row: int          # 1-based row number
    col: int          # 1-based column number
    text: str         # resolved display text
    type: str         # "n", "s", "inlineStr", "str", "b", "e", "d"


class SheetInfo(TypedDict, total=False):
    """Sheet metadata and cell grid."""

    name: str
    part: str
    rows: list[list[Cell]]
    state: str  # "visible" | "hidden" | "veryHidden"


class ParsedWorkbook(TypedDict):
    """Parsed XLSX workbook IR."""

    sheets: list[SheetInfo]
    metadata: dict
