"""Collect worksheet metadata while the row scanner consumes XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ...._utils import col_letter
from ....models import ConditionalFormat, DataValidation, FilterColumn
from ..styles.index import FormatIndex
from .rules import _parse_auto_filter_element, _parse_conditional_format_element, _parse_data_validations_element, _safe_int
from .sheet_types import NS_R, NS_S, SheetParseFlags

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
    hidden_cols: list[tuple[int, int]] = field(default_factory=list)
    merge_refs: list[str] = field(default_factory=list)
    hyperlinks: list[tuple[str, str, str]] = field(default_factory=list)
    sheet_protection: bool = False
    filter_range: str = ""
    filter_cols: list[FilterColumn] = field(default_factory=list)
    data_validations: list[DataValidation] = field(default_factory=list)
    conditional_formats: list[ConditionalFormat] = field(default_factory=list)
    blank_content_refs: list[str] = field(default_factory=list)

    def collect(self, element: ET.Element, *, format_index: FormatIndex | None) -> None:
        """Consume one completed metadata element while its children are available."""
        if element.tag == _TAG_S_MERGE_CELL:
            if ref := element.get("ref"):
                self.merge_refs.append(ref)
            element.clear()
            return
        if element.tag == _TAG_S_COL:
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
            self.filter_range, self.filter_cols = _parse_auto_filter_element(element)
            element.clear()
        elif element.tag == _TAG_S_DATA_VALIDATIONS:
            self.data_validations = _parse_data_validations_element(element)
            element.clear()
        elif element.tag == _TAG_S_CONDITIONAL_FORMATTING:
            # Conditions are not evaluated. Retain possible visible semantics.
            self.blank_content_refs.append(element.get("sqref", ""))
            self.conditional_formats.extend(_parse_conditional_format_element(element, format_index))
            element.clear()
