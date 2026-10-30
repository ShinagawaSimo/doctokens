"""Saved dynamic-array ranges, including anchors outside the retained cell window."""

from __future__ import annotations

from dataclasses import dataclass

from doctokens_core.contracts.models import ParseWarning

from ....model.workbook import Cell
from .formulas import _shared_bounds


@dataclass(frozen=True, slots=True)
class ArraySource:
    ref: str
    range: str
    bounds: tuple[int, int, int, int]


def array_source(ref: str, source_range: str, warnings: list[ParseWarning], part: str) -> ArraySource | None:
    bounds = _shared_bounds(source_range)
    anchor = _shared_bounds(ref)
    if bounds is None or anchor is None or bounds[:2] != anchor[:2]:
        warnings.append(
            ParseWarning("DYNAMIC_ARRAY_RANGE_INVALID", f"Invalid saved spill range: {source_range!r}", f"{part}!{ref}")
        )
        return None
    return ArraySource(ref, source_range, bounds)


def apply_spills(sources: list[ArraySource], cells: dict[int, Cell]) -> None:
    # Walk retained cells, never a potentially million-by-16384 source rectangle.
    for source in sources:
        left, top, right, bottom = source.bounds
        for cell in cells.values():
            if not (left <= cell["col"] <= right and top <= cell["row"] <= bottom):
                continue
            if cell["ref"] == source.ref:
                cell["dynamicArray"] = True
                if left != right or top != bottom:
                    cell["spillRange"] = source.range
            elif "formula" not in cell and "si" not in cell:
                cell["spillFrom"] = source.ref
