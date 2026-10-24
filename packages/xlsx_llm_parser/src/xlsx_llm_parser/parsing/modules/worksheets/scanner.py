"""Worksheet XML parsing for XLSX workbooks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from xml.etree import ElementTree as ET

from ooxml_llm_core.execution import checkpoint
from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageError, PackageReader
from ooxml_llm_core.xml import iterparse

from ...._utils import col_letter, parse_ref
from ....models import (
    Cell,
    RichTextRun,
)
from ....plan import XlsxParsePlan
from ..styles.index import FormatIndex
from ..workbook.rich_values import RichValueCatalog
from .cells import _parse_cell, _row_attrs
from .data_tables import read_data_table
from .formulas import SharedFormulaMaster
from .sheet_post_index import SheetPostIndex
from .sheet_types import NS_S, RowAttrs, SheetParseFlags, SheetParseResult
from .working_set import SheetWorkingSet

_ROW = f"{{{NS_S}}}row"
_CELL = f"{{{NS_S}}}c"
_FORMULA = f"{{{NS_S}}}f"
_CELL_VALUES = frozenset(f"{{{NS_S}}}{name}" for name in ("v", "t", "f"))


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
        row_sink: Callable[[int, list[Cell]], bool] | None = None,
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
        self.plan = plan
        self.warnings: list[ParseWarning] = []
        self._parse_cell = partial(
            _parse_cell,
            include_rich_text=self.flags.rich_text,
            include_style_index=self.flags.style_index,
            include_semantic_style=self.flags.semantic_style,
            include_formulas=self.flags.formulas,
            include_cell_controls=self.flags.cell_controls,
            include_display_text=self.flags.display_text,
        )
        self.cell_window = cell_window
        self.columns = plan.columns
        self.annotation_cells = plan.annotation_cells
        self.row_sink = row_sink
        self.accept_rows = True

    def parse(self) -> SheetParseResult:
        if not self.package.exists(self.sheet_part):
            raise PackageError(f"Missing worksheet part: {self.sheet_part}")

        working = SheetWorkingSet(self.flags)
        saw_root = False
        post = SheetPostIndex(self.flags)
        previous_row = 0
        ordered_rows = True
        with self.package.open_entry(self.sheet_part) as stream:
            # All cell children remain alive until their row ends. Start
            # events carry no additional information and double large-sheet
            # event traffic; processing one completed row preserves the same
            # formula dependencies and tail declarations.
            for _event, element in iterparse(stream, events=("end",)):
                saw_root = True
                if element.tag == _ROW:
                    checkpoint("reading worksheet rows")
                    attrs = _row_attrs(element)
                    number = attrs.number or previous_row + 1
                    ordered_rows = ordered_rows and number > previous_row
                    previous_row = number
                    self._read_row(element, attrs._replace(number=previous_row), working, post)
                    element.clear()
                    continue
                if element.tag == _CELL or element.tag in _CELL_VALUES:
                    continue
                post.collect(element, format_index=self.format_index)
        if not saw_root:
            raise PackageError(f"Empty worksheet part: {self.sheet_part}")
        if self.plan.formula_only and not ordered_rows:
            return WorksheetScanner(
                self.package,
                self.sheet_part,
                self.shared_strings,
                self.rich_text_map,
                self.format_index,
                self.sheet_relationships,
                self.threaded_comment_people,
                self.rich_values,
                replace(self.plan, formula_only=False),
                self.cell_window,
            ).parse()
        if self.row_sink is not None:
            return SheetParseResult(
                [],
                post.hidden_cols,
                post.sheet_protection,
                post.filter_range,
                post.filter_cols,
                post.data_validations,
                post.conditional_formats,
                self.warnings,
                post.merge_refs,
                ordered_rows,
            )
        result = working.finalize(
            post,
            self.package,
            self.sheet_relationships,
            self.threaded_comment_people,
            self.format_index,
            self.sheet_part,
            allow_annotation_cells=self.cell_window is None if self.annotation_cells is None else self.annotation_cells,
            warnings=self.warnings,
        )
        return result._replace(ordered_rows=ordered_rows)

    def _read_row(self, row: ET.Element, attrs: RowAttrs, working: SheetWorkingSet, post: SheetPostIndex) -> None:
        cells: list[Cell] | None = [] if self.accept_rows and self._includes_row(attrs.number) else None
        previous_ref = ""
        has_position = False
        if self.plan.formula_only:
            # A valid TABLE range begins at its master. Read declarations for
            # this row first so column order cannot hide cached TABLE members.
            for element in row:
                formula = element.find(_FORMULA)
                if formula is not None and formula.get("t") == "dataTable":
                    master_ref = element.get("r", "")
                    if not master_ref:
                        last_ref = ""
                        for sibling in row:
                            if sibling.tag != _CELL:
                                continue
                            column = parse_ref(last_ref)[0] if last_ref else 0
                            last_ref = sibling.get("r") or f"{col_letter(column + 1)}{attrs.number}"
                            if sibling is element:
                                master_ref = last_ref
                                break
                    working.data_tables.append(read_data_table(formula, master_ref))
        for element in row:
            if element.tag != _CELL:
                continue
            ref = element.get("r", "")
            if not ref:
                previous_col = parse_ref(previous_ref)[0] if previous_ref else 0
                ref = f"{col_letter(previous_col + 1)}{attrs.number}"
            previous_ref = ref
            formula = element.find(_FORMULA)
            if formula is not None and formula.get("ref"):
                post.blank_content_refs.append(formula.get("ref", ""))
            if self.flags.formulas and formula is not None:
                if formula.get("t") == "shared":
                    si, shared_ref = formula.get("si"), formula.get("ref")
                    if si is not None and shared_ref is not None:
                        working.add_shared_master(SharedFormulaMaster(si, ref, shared_ref, formula.text or ""))
                elif formula.get("t") == "dataTable" and not self.plan.formula_only:
                    working.data_tables.append(read_data_table(formula, ref))
            if cells is None or not self.plan.retain_cells:
                continue
            col, number = parse_ref(ref)
            if (
                self.plan.formula_only
                and formula is None
                and not any(
                    table.bounds is not None
                    and table.bounds[0] <= col <= table.bounds[2]
                    and table.bounds[1] <= attrs.number <= table.bounds[3]
                    for table in working.data_tables
                )
            ):
                continue
            if self.cell_window is not None or self.columns is not None:
                if self.cell_window is not None:
                    left, top, right, bottom = self.cell_window
                    if not (left <= col <= right and top <= number <= bottom):
                        continue
                has_position = True
                if self.columns is not None and col not in self.columns:
                    continue
            else:
                has_position = True
            cell = self._parse_cell(
                element,
                attrs,
                self.shared_strings,
                self.rich_text_map,
                self.format_index,
                ref,
                self.rich_values,
                coordinates=(col, number),
                formula_element=formula,
                decoded=True,
            )
            cells.append(cell)
            if self.row_sink is None:
                working.add_cell(cell)
        if cells is not None:
            if self.row_sink is None:
                working.add_row(cells)
                if self.package.memory_budget is not None:
                    self.package.memory_budget.add_cells(cells)
            elif has_position:
                self.accept_rows = self.row_sink(attrs.number, cells)

    def _includes_row(self, row: int) -> bool:
        if self.cell_window is None:
            return True
        _start_col, start_row, _end_col, end_row = self.cell_window
        return start_row <= row <= end_row


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
    row_sink: Callable[[int, list[Cell]], bool] | None = None,
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
        row_sink,
    ).parse()
