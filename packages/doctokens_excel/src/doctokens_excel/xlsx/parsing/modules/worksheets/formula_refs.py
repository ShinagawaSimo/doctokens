"""Translate saved A1 references without interpreting structured names as cells."""

from __future__ import annotations

import re

from ....model.coordinates import _col_from_str, col_letter

_SHEET = r"(?:'(?:[^']|'')+'|(?:\[[^\]]+\])?[\w.\\]+)"
_CELL = r"\$?[A-Za-z]{1,3}\$?[1-9][0-9]*"
_COL = r"\$?[A-Za-z]{1,3}"
_ROW = r"\$?[1-9][0-9]*"
_SEPARATOR = r"\s*:\s*"
_REFERENCE = re.compile(
    rf"(?<![\w.\\])(?P<qualifier>{_SHEET}(?:{_SEPARATOR}{_SHEET})?!)?"
    rf"(?P<reference>{_CELL}(?:{_SEPARATOR}{_CELL})?|{_COL}{_SEPARATOR}{_COL}|{_ROW}{_SEPARATOR}{_ROW})"
    r"(?![\w.\[]|\s*\()"
)
_PART = re.compile(r"(?P<ca>\$)?(?P<col>[A-Za-z]+)?(?P<ra>\$)?(?P<row>[0-9]+)?")


def _quoted_end(value: str, start: int, quote: str) -> int:
    index = start + 1
    while index < len(value):
        if value[index] == quote:
            index += 1
            if index < len(value) and value[index] == quote:
                index += 1
                continue
            return index
        index += 1
    return index


def _bracket_end(value: str, start: int) -> int:
    depth = 1
    index = start + 1
    while index < len(value) and depth:
        if value[index] == "'" and index + 1 < len(value) and value[index + 1] in "[]'#@":
            index += 2
            continue
        if value[index] == "[":
            depth += 1
        elif value[index] == "]":
            depth -= 1
        index += 1
    return index


def _shift(part: str, dc: int, dr: int) -> str:
    parsed = _PART.fullmatch(part)
    assert parsed is not None
    column, row = parsed["col"], parsed["row"]
    # In an entire-row reference the first dollar belongs to its row.
    row_abs = parsed["ra"] is not None or (not column and parsed["ca"] is not None)
    col_abs = parsed["ca"] is not None
    col_number = _col_from_str(column.upper()) if column else None
    row_number = int(row) if row else None
    if (col_number is not None and col_number > 16384) or (row_number is not None and row_number > 1048576):
        return part  # A legal defined name can resemble an out-of-grid reference.
    if col_number is not None:
        col_number += 0 if col_abs else dc
        if not 1 <= col_number <= 16384:
            return "#REF!"
    if row_number is not None:
        row_number += 0 if row_abs else dr
        if not 1 <= row_number <= 1048576:
            return "#REF!"
    return (("$" if col_abs else "") + col_letter(col_number) if col_number is not None else "") + (
        ("$" if row_abs else "") + str(row_number) if row_number is not None else ""
    )


def translate_formula(formula: str, dc: int, dr: int) -> str:
    """Shift relative cells, ranges, whole rows/columns; preserve lexical islands."""
    if dc == dr == 0:
        return formula
    parts: list[str] = []
    index = 0
    while index < len(formula):
        if formula[index] == '"':
            end = _quoted_end(formula, index, '"')
            parts.append(formula[index:end])
        elif match := _REFERENCE.match(formula, index):
            reference = re.split(r"(\s*:\s*)", match["reference"], maxsplit=1)
            shifted = _shift(reference[0], dc, dr)
            if len(reference) == 3:
                shifted += reference[1] + _shift(reference[2], dc, dr)
            parts.append((match["qualifier"] or "") + shifted)
            end = match.end()
        elif formula[index] == "[":
            end = _bracket_end(formula, index)
            parts.append(formula[index:end])
        elif formula[index] == "'":
            end = _quoted_end(formula, index, "'")
            parts.append(formula[index:end])
        else:
            parts.append(formula[index])
            end = index + 1
        index = end
    return "".join(parts)
