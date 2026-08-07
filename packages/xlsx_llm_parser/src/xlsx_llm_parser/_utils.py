"""Shared spreadsheet utilities — A1 reference parsing and column conversion.

These are used across parser, renderer, and formula expansion modules.
"""

from __future__ import annotations


def parse_ref(ref: str) -> tuple[int, int]:
    """Parse an A1-style reference into (col, row) as 1-based integers."""
    col_str = ""
    row_str = ""
    for ch in ref:
        if ch.isalpha():
            col_str += ch
        else:
            row_str += ch
    col = _col_from_str(col_str.upper())
    row = int(row_str) if row_str else 0
    return col, row


def col_letter(col: int) -> str:
    """Convert 1-based column number to A-Z letter(s)."""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def _col_from_str(s: str) -> int:
    """Convert A-Z column letter(s) to 1-based column number."""
    c = 0
    for ch in s:
        c = c * 26 + (ord(ch) - ord("A") + 1)
    return c
