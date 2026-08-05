"""XLSX parser intermediate models."""

from __future__ import annotations

from typing import TypedDict


class Cell(TypedDict, total=False):
    """A single spreadsheet cell in typed IR."""

    ref: str          # A1-style reference, e.g. "A1"
    row: int          # 1-based row number
    col: int          # 1-based column number
    text: str         # resolved display text
    type: str         # "number", "string", "boolean", "error", "date"
    formula: str      # formula text from <f> element (e.g. "SUM(A1:A10)")
    si: str           # shared formula index for slave cells
    shared_ref: str   # shared formula range (master cell only)
    formulaType: str  # "array" | "dataTable"
    formulaRange: str # array/dataTable range from <f ref=...>
    colspan: int      # merge: column span for anchor cell
    rowspan: int      # merge: row span for anchor cell
    shadow: bool      # merge: true for cells covered by a merge anchor
    spillRange: str   # dynamic array: A1-style spill range on the anchor cell
    spillFrom: str    # dynamic array: A1 ref of the source cell on spill recipients
    hidden: bool      # row hidden state
    outlineLevel: int # row outline level (0 = none)
    collapsed: bool   # row collapsed state
    hyperlink: str    # resolved URL or internal ref from <hyperlink> + rels
    style: int        # index into cellXfs for style lookup
    rich: list[dict]  # formatted text runs [{text, bold, italic, color}]


class SheetInfo(TypedDict, total=False):
    """Sheet metadata and cell grid."""

    name: str
    part: str
    kind: str      # "worksheet" | "chartsheet"
    rows: list[list[Cell]]
    state: str     # "visible" | "hidden" | "veryHidden"
    hidden_cols: list[tuple[int, int]]  # (min_col, max_col) ranges from <cols>
    sheet_protection: bool  # True when <sheetProtection> is present


class ParsedWorkbook(TypedDict):
    """Parsed XLSX workbook IR."""

    sheets: list[SheetInfo]
    metadata: dict
    fmt_index: object  # FormatIndex from formats.py
