"""Worksheet XML parsing for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageError, PackageReader
from ooxml_llm_core.xml import iterparse

from ...._utils import col_letter, coord_key, parse_ref
from ....models import (
    Cell,
    ConditionalFormat,
    DataValidation,
    FilterColumn,
    RichTextRun,
)
from ....plan import XlsxParsePlan
from ..styles.index import FormatIndex
from ..workbook.rich_values import RichValueCatalog
from .cells import _parse_cell, _row_attrs
from .comments import apply_comments
from .formulas import SharedFormulaMaster, expand_selected_shared_formulas
from .post import (
    apply_hyperlink_specs,
    apply_merge_refs,
    apply_spill_sources,
)
from .rules import _parse_auto_filter_element, _parse_conditional_format_element, _parse_data_validations_element, _safe_int
from .sheet_types import NS_R, NS_S, RowAttrs, SheetParseFlags, SheetParseResult

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

    def collect(self, element: ET.Element, *, format_index: FormatIndex | None) -> None:
        """Consume one completed metadata element while its children are available."""
        if element.tag == _TAG_S_MERGE_CELL:
            if ref := element.get("ref"):
                self.merge_refs.append(ref)
            element.clear()
            return
        if element.tag == _TAG_S_COL:
            if element.get("hidden") == "1":
                minimum = _safe_int(element.get("min"), 1)
                maximum = _safe_int(element.get("max"), minimum)
                self.hidden_cols.append((minimum, maximum))
            element.clear()
            return
        if not self.flags.sheet_rules and not self.flags.hyperlinks:
            return
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
            self.conditional_formats.extend(_parse_conditional_format_element(element, format_index))
            element.clear()


@dataclass(slots=True)
class SheetWorkingSet:
    """Row-level IR and indexes accumulated while worksheet XML is streamed."""

    flags: SheetParseFlags
    rows: list[list[Cell]] = field(default_factory=list)
    rows_by_number: dict[int, list[Cell]] = field(default_factory=dict)
    cells_by_coord: dict[int, Cell] = field(default_factory=dict)
    shared_formula_groups: dict[str, list[Cell]] = field(default_factory=dict)
    shared_formula_masters: dict[str, list[SharedFormulaMaster]] = field(default_factory=dict)
    spill_sources: list[Cell] = field(default_factory=list)

    def add_row(self, row_number: int, cells: list[Cell]) -> None:
        if not cells:
            return
        self.rows.append(cells)
        self.rows_by_number[row_number] = cells

    def add_cell(self, cell: Cell) -> None:
        self.cells_by_coord[coord_key(cell["col"], cell["row"])] = cell
        si = cell.get("si")
        if self.flags.formulas and si is not None:
            self.shared_formula_groups.setdefault(si, []).append(cell)
        if self.flags.formulas and cell.get("formulaRange") and cell.get("dynamicArray"):
            self.spill_sources.append(cell)

    def add_shared_master(self, master: SharedFormulaMaster) -> None:
        candidates = self.shared_formula_masters.setdefault(master.si, [])
        if master not in candidates and len(candidates) < 2:
            candidates.append(master)

    def finalize(
        self,
        post: SheetPostIndex,
        package: PackageReader,
        sheet_relationships: list[RelationshipRecord],
        threaded_comment_people: Mapping[str, str],
        format_index: FormatIndex | None,
        sheet_part: str,
        *,
        allow_annotation_cells: bool,
        warnings: list[ParseWarning],
    ) -> SheetParseResult:
        if self.flags.formulas:
            expand_selected_shared_formulas(self.shared_formula_groups, self.shared_formula_masters, warnings, sheet_part)
        apply_merge_refs(post.merge_refs, self.cells_by_coord)
        if self.flags.formulas:
            apply_spill_sources(self.spill_sources, self.cells_by_coord)
        annotation_rows = self.rows if allow_annotation_cells else None
        if self.flags.hyperlinks:
            apply_hyperlink_specs(
                post.hyperlinks,
                self.cells_by_coord,
                sheet_relationships,
                annotation_rows,
                self.rows_by_number if allow_annotation_cells else None,
            )
        if self.flags.comments:
            apply_comments(
                self.cells_by_coord,
                package,
                sheet_relationships,
                annotation_rows,
                self.rows_by_number if allow_annotation_cells else None,
                threaded_comment_people,
                warnings,
            )
        if allow_annotation_cells:
            self.rows.sort(key=lambda row_cells: row_cells[0]["row"] if row_cells else 0)
            for row_cells in self.rows:
                row_cells.sort(key=lambda cell: cell["col"])
        result = SheetParseResult(
            self.rows,
            post.hidden_cols,
            post.sheet_protection,
            post.filter_range,
            post.filter_cols,
            post.data_validations,
            post.conditional_formats,
            warnings,
        )
        self.cells_by_coord.clear()
        self.rows_by_number.clear()
        self.shared_formula_groups.clear()
        self.shared_formula_masters.clear()
        self.spill_sources.clear()
        return result


class WorksheetScanner:
    """Stream worksheet rows while retaining the existing complete Cell IR."""

    def __init__(
        self,
        package: PackageReader,
        sheet_part: str,
        shared_strings: list[str],
        rich_text_map: dict[int, list[RichTextRun]] | None,
        format_index: FormatIndex | None,
        sheet_relationships: list[RelationshipRecord],
        threaded_comment_people: Mapping[str, str],
        rich_values: RichValueCatalog,
        plan: XlsxParsePlan,
        cell_window: tuple[int, int, int, int] | None,
    ) -> None:
        self.package = package
        self.sheet_part = sheet_part
        self.shared_strings = shared_strings
        self.rich_text_map = rich_text_map
        self.format_index = format_index
        self.sheet_relationships = sheet_relationships
        self.threaded_comment_people = threaded_comment_people
        self.rich_values = rich_values
        self.flags = SheetParseFlags.from_plan(plan)
        self.warnings: list[ParseWarning] = []
        self._parse_cell = partial(
            _parse_cell,
            include_rich_text=self.flags.rich_text,
            include_style_index=self.flags.style_index,
            include_semantic_style=self.flags.semantic_style,
            include_formulas=self.flags.formulas,
            include_cell_controls=self.flags.cell_controls,
            warnings=self.warnings,
            sheet_part=sheet_part,
        )
        self.cell_window = cell_window

    def parse(self) -> SheetParseResult:
        if not self.package.exists(self.sheet_part):
            raise PackageError(f"Missing worksheet part: {self.sheet_part}")

        working = SheetWorkingSet(self.flags)
        saw_root = False
        post = SheetPostIndex(self.flags)
        current_attrs: RowAttrs | None = None
        current_cells: list[Cell] | None = None
        previous_col = 0
        previous_row = 0
        with self.package.open_entry(self.sheet_part) as stream:
            for event, element in iterparse(stream, events=("start", "end")):
                if event == "start":
                    saw_root = True
                    if element.tag == f"{{{NS_S}}}row":
                        raw_attrs = _row_attrs(element)
                        effective_row = raw_attrs.number or previous_row + 1
                        previous_row = effective_row
                        current_attrs = RowAttrs(effective_row, raw_attrs.hidden, raw_attrs.outline_level, raw_attrs.collapsed)
                        current_cells = [] if self._includes_row(effective_row) else None
                        previous_col = 0
                    continue
                if element.tag == f"{{{NS_S}}}c" and current_attrs is not None:
                    ref = element.get("r", "") or f"{col_letter(previous_col + 1)}{current_attrs.number}"
                    col, row = parse_ref(ref)
                    previous_col = col
                    if self.flags.formulas:
                        formula = element.find(f"{{{NS_S}}}f")
                        if formula is not None and formula.get("t") == "shared":
                            si = formula.get("si")
                            shared_ref = formula.get("ref")
                            if si is not None and shared_ref is not None:
                                working.add_shared_master(SharedFormulaMaster(si, ref, shared_ref, formula.text or ""))
                    if current_cells is not None and self._includes_cell(col, row):
                        cell = self._parse_cell(
                            element,
                            current_attrs,
                            self.shared_strings,
                            self.rich_text_map,
                            self.format_index,
                            ref,
                            self.rich_values,
                        )
                        current_cells.append(cell)
                        working.add_cell(cell)
                elif element.tag == f"{{{NS_S}}}row" and current_attrs is not None:
                    if current_cells is not None:
                        working.add_row(current_attrs.number, current_cells)
                    element.clear()
                    current_attrs = None
                    current_cells = None
                post.collect(element, format_index=self.format_index)
        if not saw_root:
            raise PackageError(f"Empty worksheet part: {self.sheet_part}")
        return working.finalize(
            post,
            self.package,
            self.sheet_relationships,
            self.threaded_comment_people,
            self.format_index,
            self.sheet_part,
            allow_annotation_cells=self.cell_window is None,
            warnings=self.warnings,
        )

    def _includes_row(self, row: int) -> bool:
        if self.cell_window is None:
            return True
        _start_col, start_row, _end_col, end_row = self.cell_window
        return start_row <= row <= end_row

    def _includes_cell(self, col: int, row: int) -> bool:
        if self.cell_window is None:
            return True
        start_col, start_row, end_col, end_row = self.cell_window
        return start_col <= col <= end_col and start_row <= row <= end_row


def parse_sheet(
    package: PackageReader,
    sheet_part: str,
    shared_strings: list[str],
    rich_text_map: dict[int, list[RichTextRun]] | None = None,
    format_index: FormatIndex | None = None,
    sheet_relationships: list[RelationshipRecord] | None = None,
    threaded_comment_people: Mapping[str, str] | None = None,
    rich_values: RichValueCatalog | None = None,
    plan: XlsxParsePlan | None = None,
    cell_window: tuple[int, int, int, int] | None = None,
) -> SheetParseResult:
    """Parse a worksheet XML part into typed cell rows and sheet-level metadata."""
    return WorksheetScanner(
        package,
        sheet_part,
        shared_strings,
        rich_text_map,
        format_index,
        sheet_relationships or [],
        threaded_comment_people or {},
        rich_values or RichValueCatalog(),
        plan or XlsxParsePlan.session(),
        cell_window,
    ).parse()
