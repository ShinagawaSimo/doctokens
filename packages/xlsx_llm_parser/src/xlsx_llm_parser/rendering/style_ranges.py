"""Style ranges."""

from __future__ import annotations

from .._utils import col_letter
from ..models import Cell
from ..parsing.modules.styles.index import FormatIndex

_STYLE_RANGE_MIN_CELLS = 6


def _style_range_records(
    rows: list[list[Cell]],
    format_index: FormatIndex,
) -> tuple[list[tuple[str, dict[str, object]]], set[str]]:
    cells_by_style: dict[str, set[tuple[int, int]]] = {}
    for row in rows:
        for cell in row:
            if cell.get("shadow") or cell.get("style") is None:
                continue
            style = format_index.style_attrs(cell.get("style"))
            if "color=" not in style and "fill=" not in style:
                continue
            cells = cells_by_style.setdefault(style, set())
            for row_number in range(cell["row"], cell["row"] + cell.get("rowspan", 1)):
                for column_number in range(cell["col"], cell["col"] + cell.get("colspan", 1)):
                    cells.add((row_number, column_number))
    suppressed = {style for style, cells in cells_by_style.items() if len(cells) >= _STYLE_RANGE_MIN_CELLS}
    records: list[tuple[str, dict[str, object]]] = []
    for style in sorted(suppressed):
        attrs: dict[str, object] = {}
        _add_style_attrs(attrs, style)
        for start_col, first_row, end_col, last_row in _rectangular_ranges(cells_by_style[style]):
            records.append((_range_ref(start_col, first_row, end_col, last_row), attrs))
    return records, suppressed


def _rectangular_ranges(cells: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    spans_by_row = {
        row: _horizontal_spans(sorted(column for item_row, column in cells if item_row == row))
        for row in sorted({item_row for item_row, _column in cells})
    }
    finished: list[tuple[int, int, int, int]] = []
    active: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for row, spans in spans_by_row.items():
        current = set(spans)
        for start_col, end_col in spans:
            key = (start_col, end_col)
            previous = active.get(key)
            if previous is not None and previous[3] == row - 1:
                active[key] = (previous[0], previous[1], previous[2], row)
            else:
                if previous is not None:
                    finished.append(previous)
                active[key] = (start_col, row, end_col, row)
        expired = [key for key in active if key not in current and active[key][3] < row]
        finished.extend(active.pop(key) for key in expired)
    finished.extend(active.values())
    return sorted(finished, key=lambda item: (item[1], item[0], item[3], item[2]))


def _horizontal_spans(columns: list[int]) -> list[tuple[int, int]]:
    if not columns:
        return []
    spans: list[tuple[int, int]] = []
    start = previous = columns[0]
    for column in columns[1:]:
        if column == previous + 1:
            previous = column
            continue
        spans.append((start, previous))
        start = previous = column
    spans.append((start, previous))
    return spans


def _range_ref(start_col: int, start_row: int, end_col: int, end_row: int) -> str:
    start = f"{col_letter(start_col)}{start_row}"
    end = f"{col_letter(end_col)}{end_row}"
    return start if start == end else f"{start}:{end}"


def _add_style_attrs(attrs: dict[str, object], value: str) -> None:
    for item in value.split():
        if item in {"bold", "italic", "underline"}:
            attrs[item] = True
        elif "=" in item:
            key, style_value = item.split("=", 1)
            attrs[key] = style_value
