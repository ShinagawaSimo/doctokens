"""Collect worksheet metadata while the row scanner consumes XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from doctokens_core.contracts.models import ParseWarning

from ....model.coordinates import col_letter
from ....model.rules import ConditionalFormat, DataValidation, FilterColumn
from ..styles.index import FormatIndex
from .conditional_formats import merge_conditional_formats, parse_conditional_formats
from .filters import _parse_auto_filter_element
from .rule_values import X14, XM
from .rule_values import integer as _safe_int
from .sheet_types import NS_R, NS_S, SheetParseFlags
from .validations import parse_validations

_TAG_S_COL = f"{{{NS_S}}}col"
_TAG_S_MERGE_CELL = f"{{{NS_S}}}mergeCell"
_TAG_S_HYPERLINK = f"{{{NS_S}}}hyperlink"
_TAG_S_SHEET_PROTECTION = f"{{{NS_S}}}sheetProtection"
_TAG_S_AUTO_FILTER = f"{{{NS_S}}}autoFilter"
_TAG_S_DATA_VALIDATIONS = f"{{{NS_S}}}dataValidations"
_TAG_S_CONDITIONAL_FORMATTING = f"{{{NS_S}}}conditionalFormatting"


@dataclass(slots=True)
class SheetPostIndex:
    """Small sheet-level declarations collected during the primary XML scan."""

    flags: SheetParseFlags
    warnings: list[ParseWarning] = field(default_factory=list)
    part: str = ""
    hidden_cols: list[tuple[int, int]] = field(default_factory=list)
    merge_refs: list[str] = field(default_factory=list)
    hyperlinks: list[tuple[str, str, str]] = field(default_factory=list)
    sheet_protection: bool = False
    filter_range: str = ""
    filter_cols: list[FilterColumn] = field(default_factory=list)
    data_validations: list[DataValidation] = field(default_factory=list)
    conditional_formats: list[ConditionalFormat] = field(default_factory=list)
    extended_formats: list[ConditionalFormat] = field(default_factory=list)
    blank_content_refs: list[str] = field(default_factory=list)
    column_styles: list[tuple[int, int, int]] = field(default_factory=list)
    _column_style_cache: dict[int, int | None] = field(default_factory=dict)

    def column_style(self, column: int) -> int | None:
        if column not in self._column_style_cache:
            self._column_style_cache[column] = next(
                (style for first, last, style in reversed(self.column_styles) if first <= column <= last), None
            )
        return self._column_style_cache[column]

    def collect(self, element: ET.Element, *, format_index: FormatIndex | None) -> None:
        """Consume one completed metadata element while its children are available."""
        if element.tag == _TAG_S_MERGE_CELL:
            if ref := element.get("ref"):
                self.merge_refs.append(ref)
            element.clear()
            return
        if element.tag == _TAG_S_COL:
            if element.get("style") is not None:
                self._column_style_cache.clear()
                self.column_styles.append(
                    (_safe_int(element.get("min"), 1), _safe_int(element.get("max"), 1), _safe_int(element.get("style"), 0))
                )
            if (
                format_index is not None
                and element.get("style") is not None
                and format_index.preserves_blank(_safe_int(element.get("style"), -1))
            ):
                first = _safe_int(element.get("min"), 1)
                last = _safe_int(element.get("max"), first)
                self.blank_content_refs.append(f"{col_letter(first)}1:{col_letter(last)}1048576")
            if element.get("hidden") == "1":
                minimum = _safe_int(element.get("min"), 1)
                maximum = _safe_int(element.get("max"), minimum)
                self.hidden_cols.append((minimum, maximum))
            element.clear()
            return
        if element.tag == _TAG_S_HYPERLINK:
            self.blank_content_refs.append(element.get("ref", ""))
        if element.tag == _TAG_S_HYPERLINK and self.flags.hyperlinks:
            self.hyperlinks.append((element.get("ref", ""), element.get(f"{{{NS_R}}}id", ""), element.get("location", "")))
            element.clear()
            return
        if not self.flags.sheet_rules:
            return
        if element.tag == _TAG_S_SHEET_PROTECTION:
            self.sheet_protection = True
        elif element.tag == _TAG_S_AUTO_FILTER:
            self.filter_range, self.filter_cols = _parse_auto_filter_element(element, format_index)
            element.clear()
        elif element.tag in {_TAG_S_DATA_VALIDATIONS, f"{{{X14}}}dataValidations"}:
            self.data_validations.extend(parse_validations(element, self.warnings, self.part))
            element.clear()
        elif element.tag in {_TAG_S_CONDITIONAL_FORMATTING, f"{{{X14}}}conditionalFormatting"}:
            # Conditions are not evaluated. Retain possible visible semantics.
            extended = element.tag == f"{{{X14}}}conditionalFormatting"
            ranges = element.findtext(f"{{{XM}}}sqref", "") if extended else element.get("sqref", "")
            self.blank_content_refs.append(ranges)
            target = self.extended_formats if extended else self.conditional_formats
            target.extend(parse_conditional_formats(element, format_index, self.warnings, self.part))
            element.clear()

    def finish(self) -> None:
        self.conditional_formats = merge_conditional_formats(self.conditional_formats, self.extended_formats)
        for rule in self.conditional_formats:
            kind = rule.get("ruleType")
            missing_formula = kind in {"cellIs", "expression"} and not rule.get("formulas")
            missing_visual = kind in {"colorScale", "dataBar", "iconSet"} and not rule.get("formatKind")
            if not rule.get("ranges") or not kind or missing_formula or missing_visual:
                rule["unparsed"] = True
                self.warnings.append(
                    ParseWarning(
                        "CONDITIONAL_FORMAT_UNSUPPORTED", "Conditional format lacks a saved type, range or body", self.part
                    )
                )
        unique: list[DataValidation] = []
        for validation in self.data_validations:
            if validation not in unique:
                unique.append(validation)
        self.data_validations = unique
