"""Lightweight extent scan and bounded preview state for independent saved cells."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field

from doctokens_core.containers.opc.models import RelationshipRecord
from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.runtime.execution import checkpoint

from ....model.coordinates import col_letter, parse_ref
from ....model.workbook import Cell
from ....rendering._constants import _CELL_BUDGET
from ..styles.index import FormatIndex
from .cells import _blank_candidate, _row_attrs, effective_style
from .sheet_post_index import SheetPostIndex
from .sheet_types import NS_S, SheetParseFlags
from .xml_stream import iter_sheet_elements

_ROW = f"{{{NS_S}}}row"
_CELL = f"{{{NS_S}}}c"
_FORMULA = f"{{{NS_S}}}f"
_VALUE = f"{{{NS_S}}}v"
_SHEET_DATA = f"{{{NS_S}}}sheetData"


@dataclass(slots=True)
class PreviewState:
    right: int
    bottom: int
    density: str
    hidden_cols: list[tuple[int, int]]
    count: int = 0
    next_row: int | None = None
    shared_string_indices: set[int] | None = field(default_factory=set)

    @property
    def accepting(self) -> bool:
        return self.count < _CELL_BUDGET

    def include(self, cells: list[Cell]) -> None:
        # The extent is global. Do not reclassify an internal blank as a tail
        # merely because its later meaningful neighbour was not materialized.
        for cell in cells:
            cell.pop("blankCandidate", None)
        self.count += sum(
            self.density != "plain" or not any(first <= cell["col"] <= last for first, last in self.hidden_cols) for cell in cells
        )

    def observe_next(self, ref: str, number: int) -> None:
        if self.next_row is None and number <= self.bottom and parse_ref(ref)[0] <= self.right:
            self.next_row = number


@dataclass(frozen=True, slots=True)
class PreparedPreview:
    """A completed preflight, including an explicit compatibility-path decision."""

    state: PreviewState | None


def preview_state(
    package: PackageReader,
    part: str,
    formats: FormatIndex | None,
    flags: SheetParseFlags,
    relationships: list[RelationshipRecord],
    density: str,
) -> PreviewState | None:
    """Find the real saved extent without resolving values or retaining rows.

    Dependent-cell features currently use the complete compatibility path.
    They must not be approximated using declared rectangular dimensions.
    """
    if any(rel.type.endswith(("/comments", "/threadedComment")) for rel in relationships):
        return None
    post = SheetPostIndex(flags)
    previous_row = right = bottom = 0
    indices: set[int] = set()
    mandatory_cells = 0
    with package.open_entry(part) as stream:
        for element in iter_sheet_elements(stream):
            if element.tag == _ROW:
                checkpoint("finding worksheet reading extent")
                attrs = _row_attrs(element)
                number = attrs.number or previous_row + 1
                if number <= previous_row:
                    return None
                previous_row = number
                attrs = attrs._replace(number=number)
                previous_col = 0
                collect = mandatory_cells < _CELL_BUDGET
                row_mandatory = 0
                for cell in element:
                    if cell.tag != _CELL:
                        continue
                    ref = cell.get("r") or f"{col_letter(previous_col + 1)}{number}"
                    column, source_row = parse_ref(ref)
                    previous_col = column
                    if source_row != number:
                        return None
                    formula = cell.find(_FORMULA)
                    if formula is not None and (formula.get("ref") or formula.get("t") in {"array", "dataTable", "shared"}):
                        return None
                    kind = cell.get("t", "n")
                    value = cell.find(_VALUE)
                    blank = False
                    if kind == "n" and (value is None or not value.text):
                        style = effective_style(cell, attrs, post.column_style(column))
                        blank = _blank_candidate(cell, kind, value, attrs, style, formats)
                        if formats is not None and flags.cell_controls and formats.cell_control(style):
                            blank = False
                    if not blank:
                        right, bottom = max(right, column), max(bottom, number)
                        if collect:
                            row_mandatory += 1
                    if collect and kind == "s" and value is not None and value.text:
                        with suppress(ValueError):
                            index = int(value.text)
                            if index >= 0:
                                indices.add(index)
                mandatory_cells += row_mandatory
                element.clear()
            elif element.tag == _SHEET_DATA:
                element.clear()
            elif element.tag not in {_CELL, _FORMULA, _VALUE}:
                post.collect(element, format_index=formats)
                if post.merge_refs or post.blank_content_refs:
                    return None
    state = PreviewState(right, bottom, density, post.hidden_cols)
    # Mandatory cells are a safe lower bound: retained internal blanks can
    # make the actual preview end earlier. Hidden columns need a later plan.
    state.shared_string_indices = None if density == "plain" and post.hidden_cols else indices
    return state
