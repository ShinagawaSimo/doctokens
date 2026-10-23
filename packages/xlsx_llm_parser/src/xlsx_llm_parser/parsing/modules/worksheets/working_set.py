"""Retained worksheet cells and dependency indexes for ordinary render/session plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ooxml_llm_core.models import ParseWarning, RelationshipRecord
from ooxml_llm_core.package import PackageReader

from ...._utils import coord_key
from ....models import Cell
from ..styles.index import FormatIndex
from .blank_cells import preserve_blank_ranges
from .comments import apply_comments
from .data_tables import DataTableFormula, apply_data_tables
from .formulas import SharedFormulaMaster, expand_selected_shared_formulas
from .post import apply_hyperlink_specs, apply_merge_refs, apply_spill_sources
from .sheet_post_index import SheetPostIndex
from .sheet_types import SheetParseFlags, SheetParseResult


@dataclass(slots=True)
class SheetWorkingSet:
    """Row-level IR and indexes accumulated while worksheet XML is streamed."""

    flags: SheetParseFlags
    rows: list[list[Cell]] = field(default_factory=list)
    rows_by_number: dict[int, list[Cell]] = field(default_factory=dict)
    cells_by_coord: dict[int, Cell] = field(default_factory=dict)
    shared_formula_groups: dict[str, list[Cell]] = field(default_factory=dict)
    shared_formula_masters: dict[str, list[SharedFormulaMaster]] = field(default_factory=dict)
    data_tables: list[DataTableFormula] = field(default_factory=list)
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
            apply_data_tables(self.data_tables, self.rows_by_number, warnings, sheet_part)
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
        preserve_blank_ranges(self.rows, post.blank_content_refs)
        result = SheetParseResult(
            self.rows,
            post.hidden_cols,
            post.sheet_protection,
            post.filter_range,
            post.filter_cols,
            post.data_validations,
            post.conditional_formats,
            warnings,
            post.merge_refs,
        )
        self.cells_by_coord.clear()
        self.rows_by_number.clear()
        self.shared_formula_groups.clear()
        self.shared_formula_masters.clear()
        self.data_tables.clear()
        self.spill_sources.clear()
        return result
