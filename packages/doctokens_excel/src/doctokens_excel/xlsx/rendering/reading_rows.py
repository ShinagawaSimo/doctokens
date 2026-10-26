"""Suppress only saved, meaningless blanks beyond the reading extent.

The parsed rows remain intact for queries and explicit cell-range requests.
Classification runs after worksheet relationships have been attached.
"""

from __future__ import annotations

from ..model.workbook import Cell

_CONTENT_KEYS = frozenset(
    {
        "formula",
        "si",
        "formulaType",
        "formulaRange",
        "spillRange",
        "spillFrom",
        "colspan",
        "rowspan",
        "shadow",
        "hyperlink",
        "comment",
        "threadedComments",
        "richValue",
        "cellControl",
        "rich",
        "raw",
    }
)


def _residual(cell: Cell) -> bool:
    return bool(cell.get("blankCandidate")) and not cell.get("text") and _CONTENT_KEYS.isdisjoint(cell)


def reading_rows(rows: list[list[Cell]]) -> list[list[Cell]]:
    """Retain internal blanks and source coordinates; never mutate query IR."""
    max_row = max_col = 0
    for row in rows:
        for cell in row:
            if not _residual(cell):
                max_row = max(max_row, cell["row"])
                max_col = max(max_col, cell["col"])
    result: list[list[Cell]] = []
    for row in rows:
        retained = [cell for cell in row if not _residual(cell) or (cell["row"] <= max_row and cell["col"] <= max_col)]
        if retained:
            result.append(retained)
    return result
