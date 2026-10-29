"""Shared formula expansion — resolve ``si`` references to per-cell formula text.

OOXML stores shared formulas as one master formula with a ``ref`` range
and slave cells that reference the master by ``si`` index.  This module
expands each slave to its own formula by applying row/column offsets.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from doctokens_core.contracts.models import ParseWarning

from ....model.coordinates import _col_from_str
from ....model.workbook import Cell
from .formula_refs import translate_formula

# A1-style cell reference: $A$1, $A1, A$1, A1  (optionally qualified by sheet)
_CELL_REF_RE = re.compile(r"(?P<col_abs>\$)?(?P<col>[A-Z]{1,3})(?P<row_abs>\$)?(?P<row>[0-9]+)", re.IGNORECASE)


class SharedFormulaMaster(NamedTuple):
    si: str
    ref: str
    shared_ref: str
    formula: str


_SHARED_RANGE_RE = re.compile(r"[A-Za-z]{1,3}[1-9][0-9]*(?::[A-Za-z]{1,3}[1-9][0-9]*)?")


def expand_selected_shared_formulas(
    groups: dict[str, list[Cell]],
    masters: dict[str, list[SharedFormulaMaster]],
    warnings: list[ParseWarning],
    sheet_part: str,
) -> None:
    """Expand retained cells using compact masters from the entire worksheet."""
    for si, group in groups.items():
        candidates = masters.get(si, [])
        affected = next((cell for cell in group if not cell.get("shared_ref")), None)
        if affected is None:
            continue
        locator = f"{sheet_part}!{affected['ref']}"
        if not candidates:
            warnings.append(ParseWarning("SHARED_FORMULA_UNRESOLVED", f"Shared formula {si!r} has no master", locator))
            continue
        if len(candidates) != 1:
            warnings.append(ParseWarning("SHARED_FORMULA_INVALID", f"Shared formula {si!r} has conflicting masters", locator))
            continue
        master = candidates[0]
        bounds = _shared_bounds(master.shared_ref)
        if bounds is None:
            warnings.append(ParseWarning("SHARED_FORMULA_INVALID", f"Shared formula {si!r} has an invalid range", locator))
            continue
        start_col, start_row, end_col, end_row = bounds
        master_col, master_row = _col_row(master.ref)
        if not (start_col <= master_col <= end_col and start_row <= master_row <= end_row) or any(
            not (start_col <= cell["col"] <= end_col and start_row <= cell["row"] <= end_row) for cell in group
        ):
            warnings.append(
                ParseWarning("SHARED_FORMULA_INVALID", f"Shared formula {si!r} has a cell outside its range", locator)
            )
            continue
        if not master.formula:
            warnings.append(ParseWarning("SHARED_FORMULA_UNRESOLVED", f"Shared formula {si!r} has no master text", locator))
            continue
        selected_slaves = [cell for cell in group if cell["ref"] != master.ref]
        for cell in selected_slaves:
            cell["formula"] = translate_formula(master.formula, cell["col"] - master_col, cell["row"] - master_row)


def _shared_bounds(value: str) -> tuple[int, int, int, int] | None:
    if not _SHARED_RANGE_RE.fullmatch(value):
        return None
    start, _, end = value.partition(":")
    start_col, start_row = _col_row(start)
    end_col, end_row = _col_row(end or start)
    if not (1 <= start_col <= end_col <= 16384 and 1 <= start_row <= end_row <= 1048576):
        return None
    return start_col, start_row, end_col, end_row


def _col_row(ref: str) -> tuple[int, int]:
    match = _CELL_REF_RE.fullmatch(ref.replace("$", ""))
    return (_col_from_str(match["col"].upper()), int(match["row"])) if match else (0, 0)
