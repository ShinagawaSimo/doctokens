"""Reconstruct What-If TABLE formulas and retain their result-group semantics."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from ooxml_llm_core.models import ParseWarning

from ...._utils import parse_ref
from ....models import Cell

_CELL_REF = re.compile(r"\$?[A-Za-z]{1,3}\$?[1-9][0-9]{0,6}")


@dataclass(frozen=True, slots=True)
class DataTableFormula:
    master_ref: str
    result_range: str
    bounds: tuple[int, int, int, int] | None
    formula: str | None
    problem: str | None


def read_data_table(element: ET.Element, master_ref: str) -> DataTableFormula:
    """Decode attributes on the master; TABLE text is not stored in its f node."""
    result_range = element.get("ref", "")
    bounds = None
    try:
        start, _, end = result_range.partition(":")
        if ":" in result_range and not end:
            raise ValueError("ref has an empty range endpoint")
        start_col, start_row = _point(start)
        end_col, end_row = _point(end or start)
        if start_col > end_col or start_row > end_row or _point(master_ref) != (start_col, start_row):
            raise ValueError("ref must start at the master and have ordered bounds")
        bounds = start_col, start_row, end_col, end_row
        two_inputs = _boolean(element, "dt2D")
        first = _input(element, "r1", "del1")
        if two_inputs:
            # OOXML r1 is the column input, r2 the row input. TABLE takes row first.
            second = _input(element, "r2", "del2")
            formula = f"TABLE({second},{first})"
        elif _boolean(element, "dtr"):
            formula = f"TABLE({first},)"
        else:
            formula = f"TABLE(,{first})"
    except ValueError as exc:
        return DataTableFormula(master_ref, result_range, bounds, None, str(exc))
    return DataTableFormula(master_ref, result_range, bounds, formula, None)


def _point(value: str) -> tuple[int, int]:
    if not _CELL_REF.fullmatch(value):
        raise ValueError(f"Missing or invalid cell reference: {value!r}")
    col, row = parse_ref(value.replace("$", "").upper())
    if col > 16384 or row > 1048576:
        raise ValueError(f"Cell reference exceeds worksheet bounds: {value!r}")
    return col, row


def _boolean(element: ET.Element, name: str) -> bool:
    value = element.get(name, "false").strip()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(f"Invalid {name} boolean: {value!r}")
    return value in {"true", "1"}


def _input(element: ET.Element, name: str, deleted: str) -> str:
    if _boolean(element, deleted):
        return "#REF!"
    value = element.get(name, "")
    _point(value)
    return value.upper()


def apply_data_tables(
    tables: list[DataTableFormula],
    rows: dict[int, list[Cell]],
    warnings: list[ParseWarning],
    sheet_part: str,
) -> None:
    """Annotate retained cells without materializing missing or unselected cells.

    Each member retains the same formula and original range in IR. Renderers can
    emit the group once in a full sheet or a selection that excludes its master.
    """
    if not tables:
        return
    row_numbers = sorted(rows)
    members: list[list[Cell]] = []
    owners: dict[str, int] = {}
    conflicts: set[int] = set()
    for index, table in enumerate(tables):
        selected: list[Cell] = []
        if table.bounds is None:
            selected = [cell for row in rows.values() for cell in row if cell["ref"] == table.master_ref]
        else:
            left, top, right, bottom = table.bounds
            for row_number in row_numbers[bisect_left(row_numbers, top) : bisect_right(row_numbers, bottom)]:
                selected.extend(cell for cell in rows[row_number] if left <= cell["col"] <= right)
        for cell in selected:
            previous = owners.get(cell["ref"])
            if previous is not None:
                conflicts.update((previous, index))
            owners[cell["ref"]] = index
            if cell["ref"] != table.master_ref and ("formula" in cell or "formulaType" in cell or "si" in cell):
                conflicts.add(index)
        members.append(selected)

    cache_warnings = {item.locator for item in warnings if item.code == "XLSX_FORMULA_BAR_UNAVAILABLE"}
    resolved_cache_warnings: set[str] = set()
    for index, (table, selected) in enumerate(zip(tables, members, strict=True)):
        if not selected:
            continue
        problem = "Conflicting formulas in data table result range" if index in conflicts else table.problem
        if problem:
            warnings.append(ParseWarning("DATA_TABLE_FORMULA_INVALID", problem, f"{sheet_part}!{selected[0]['ref']}"))
        if index in conflicts:
            continue
        for cell in selected:
            cell["formulaType"] = "dataTable"
            if table.result_range:
                cell["formulaRange"] = table.result_range
            if table.formula is not None:
                cell["formula"] = table.formula
            # These v nodes are cached results, not editable literal inputs.
            cell.pop("raw", None)
            locator = f"{sheet_part}!{cell['ref']}"
            if locator in cache_warnings:
                resolved_cache_warnings.add(locator)
    if resolved_cache_warnings:
        warnings[:] = [
            item
            for item in warnings
            if item.code != "XLSX_FORMULA_BAR_UNAVAILABLE" or item.locator not in resolved_cache_warnings
        ]
