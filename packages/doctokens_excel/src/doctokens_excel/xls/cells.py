"""BIFF8 stored cell values, including formula result association."""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from struct import pack, unpack_from

from .formats import XlsFormatIndex
from .models import XlsCell, XlsError
from .records import Cursor, Record, read_bof
from .strings import read_formula_string

_ERRORS = {0: "#NULL!", 7: "#DIV/0!", 15: "#VALUE!", 23: "#REF!", 29: "#NAME?", 36: "#NUM!", 42: "#N/A"}
_VALUES = {0x00FD, 0x0203, 0x027E, 0x00BD, 0x0205, 0x0006}


def number(value: float) -> float:
    if not math.isfinite(value) or 0 < abs(value) < sys.float_info.min or (value == 0 and math.copysign(1, value) < 0):
        raise XlsError("Invalid BIFF Xnum value")
    return value


def rk(data: bytes, offset: int) -> float:
    value = unpack_from("<I", data, offset)[0]
    if value & 2:
        decoded = float(unpack_from("<i", data, offset)[0] >> 2)
    else:
        decoded = unpack_from("<d", pack("<II", 0, value & 0xFFFFFFFC))[0]
    return number(decoded / 100 if value & 1 else decoded)


def error(value: int) -> str:
    if value not in _ERRORS:
        raise XlsError(f"Unknown XLS error value: {value}")
    return _ERRORS[value]


def _cell(data: bytes, kind: str, value: str | float | bool, *, formula: bool = False) -> XlsCell:
    row, column, xf = unpack_from("<3H", data)
    if column > 255:
        raise XlsError("XLS column outside BIFF8 range")
    if kind == "string":
        return XlsCell(row + 1, column + 1, "string", value, xf, formula)
    if kind == "boolean":
        return XlsCell(row + 1, column + 1, "boolean", value, xf, formula)
    if kind == "error":
        return XlsCell(row + 1, column + 1, "error", value, xf, formula)
    return XlsCell(row + 1, column + 1, "number", value, xf, formula)


def _value_cells(cursor: Cursor, record: Record, strings: list[str]) -> list[XlsCell]:
    minimum = {0x00FD: 10, 0x0203: 14, 0x027E: 10, 0x00BD: 18, 0x0205: 8, 0x0006: 22}[record.kind]
    data = cursor.payload(record, minimum)
    if record.kind == 0x00FD:
        index = unpack_from("<I", data, 6)[0]
        if index >= len(strings):
            raise XlsError("XLS shared-string index is out of range")
        return [_cell(data, "string", strings[index])]
    if record.kind == 0x0203:
        return [_cell(data, "number", number(unpack_from("<d", data, 6)[0]))]
    if record.kind == 0x027E:
        return [_cell(data, "number", rk(data, 6))]
    if record.kind == 0x00BD:
        row, first = unpack_from("<HH", data)
        last = unpack_from("<H", data, len(data) - 2)[0]
        if not first < last <= 255 or len(data) != 6 + 6 * (last - first + 1):
            raise XlsError("Invalid XLS MulRk count or column range")
        result = []
        for index, column in enumerate(range(first, last + 1)):
            offset = 4 + 6 * index
            xf = unpack_from("<H", data, offset)[0]
            result.append(XlsCell(row + 1, column + 1, "number", rk(data, offset + 2), xf))
        return result
    if record.kind == 0x0205:
        if data[7] not in (0, 1) or (data[7] == 0 and data[6] not in (0, 1)):
            raise XlsError("Invalid XLS boolean/error discriminator")
        return [_cell(data, "error", error(data[6])) if data[7] else _cell(data, "boolean", bool(data[6]))]
    token_count = unpack_from("<H", data, 20)[0]
    if token_count > len(data) - 22:
        raise XlsError("Truncated XLS formula tokens")
    cached = data[6:14]
    if cached[6:] != b"\xff\xff":
        return [_cell(data, "number", number(unpack_from("<d", cached)[0]), formula=True)]
    kind = cached[0]
    if kind in (0, 3):
        return [_cell(data, "string", "", formula=True)]
    if kind == 1 and cached[2] in (0, 1):
        return [_cell(data, "boolean", bool(cached[2]), formula=True)]
    if kind == 2:
        return [_cell(data, "error", error(cached[2]), formula=True)]
    raise XlsError("Invalid XLS formula cached-result type")


def read_cells(cursor: Cursor, strings: list[str], formats: XlsFormatIndex) -> tuple[XlsCell, ...] | None:
    read_bof(cursor, 0x0010)
    cells: dict[tuple[int, int], XlsCell] = {}
    pending: XlsCell | None = None
    depth = 0
    while True:
        record = cursor.next()
        if depth:
            if record.kind == 0x0809:
                depth += 1
            elif record.kind == 0x000A:
                depth -= 1
            if depth > 32:
                raise XlsError("XLS nested substreams exceed the depth limit")
            continue
        if pending is not None:
            if record.kind == 0x0207:
                cell = formats.format_cell(replace(pending, value=read_formula_string(cursor, record)))
                cells[(cell.row, cell.column)] = cell
                pending = None
                continue
            if record.kind in (0x04BC, 0x0221, 0x0236):
                continue
            raise XlsError("Missing String record after XLS formula")
        if record.kind == 0x0809:
            depth = 1
        elif record.kind == 0x000A:
            return tuple(cells[key] for key in sorted(cells))
        elif record.kind == 0x0081:
            if unpack_from("<H", cursor.payload(record, 2))[0] & 0x0010:
                return None  # Dialog sheets are outside the ordinary worksheet scope.
        elif record.kind in (0x0204, 0x00D6):
            raise XlsError("Inline Label/RString compatibility records are not supported yet")
        elif record.kind in _VALUES:
            for cell in _value_cells(cursor, record, strings):
                cell = formats.format_cell(cell)
                key = (cell.row, cell.column)
                if key in cells:
                    raise XlsError(f"Duplicate XLS cell {cell.ref}")
                cursor.budget.cells += 1
                if cursor.budget.cells > cursor.budget.limits.max_cells:
                    raise XlsError("XLS exceeds max_cells")
                cells[key] = cell
                if record.kind == 0x0006:
                    cached = cursor.payload(record)[6:14]
                    if cached[6:] == b"\xff\xff" and cached[0] == 0:
                        pending = cell
