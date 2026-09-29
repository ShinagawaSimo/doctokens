"""Post common."""

from __future__ import annotations

from ooxml_llm_core.models import ParseWarning

from ...._utils import coord_key
from ....models import (
    Cell,
)

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _warn(warnings: list[ParseWarning] | None, code: str, message: str, locator: str) -> None:
    if warnings is not None:
        warnings.append(ParseWarning(code, message, locator))


def _ensure_cell(
    cell_map: dict[int, Cell],
    rows: list[list[Cell]] | None,
    rows_by_number: dict[int, list[Cell]] | None,
    ref: str,
    col: int,
    row: int,
) -> Cell | None:
    """Materialize an otherwise empty annotated/navigable cell so its semantics remain visible."""
    existing = cell_map.get(coord_key(col, row))
    if existing is not None:
        return existing
    if rows is None:
        return None
    cell: Cell = {"ref": ref, "col": col, "row": row, "text": ""}
    cell_map[coord_key(col, row)] = cell
    target_row = rows_by_number.get(row) if rows_by_number is not None else None
    if target_row is None:
        target_row = [cell]
        rows.append(target_row)
        if rows_by_number is not None:
            rows_by_number[row] = target_row
    else:
        target_row.append(cell)
    return cell


def _as_bool(value: str | None) -> bool:
    return value is not None and value.lower() not in {"0", "false", "off", "none"}


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
