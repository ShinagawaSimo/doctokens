"""Sheet types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from ooxml_llm_core.models import ParseWarning

from ....models import (
    Cell,
    ConditionalFormat,
    DataValidation,
    FilterColumn,
)
from ....plan import XlsxFeature, XlsxParsePlan

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class SheetParseResult(NamedTuple):
    rows: list[list[Cell]]
    hidden_cols: list[tuple[int, int]]
    sheet_protection: bool
    filter_range: str
    filter_cols: list[FilterColumn]
    data_validations: list[DataValidation]
    conditional_formats: list[ConditionalFormat]
    warnings: list[ParseWarning]


class RowAttrs(NamedTuple):
    number: int
    hidden: bool
    outline_level: int
    collapsed: bool


@dataclass(frozen=True, slots=True)
class SheetParseFlags:
    """Hot-loop booleans derived once from an XLSX parse plan."""

    formulas: bool
    hyperlinks: bool
    comments: bool
    sheet_rules: bool
    rich_text: bool
    style_index: bool
    semantic_style: bool
    cell_controls: bool

    @classmethod
    def from_plan(cls, plan: XlsxParsePlan) -> SheetParseFlags:
        return cls(
            formulas=plan.needs(XlsxFeature.FORMULAS),
            hyperlinks=plan.needs(XlsxFeature.HYPERLINKS),
            comments=plan.needs(XlsxFeature.COMMENTS),
            sheet_rules=plan.needs(XlsxFeature.SHEET_RULES),
            rich_text=plan.needs(XlsxFeature.RICH_TEXT),
            style_index=plan.needs(XlsxFeature.STYLE_INDEX),
            semantic_style=plan.needs(XlsxFeature.SEMANTIC_STYLES),
            cell_controls=plan.needs(XlsxFeature.CELL_CONTROLS),
        )
