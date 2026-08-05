"""Shared formula expansion — resolve ``si`` references to per-cell formula text.

OOXML stores shared formulas as one master formula with a ``ref`` range
and slave cells that reference the master by ``si`` index.  This module
expands each slave to its own formula by applying row/column offsets.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# A1-style cell reference: $A$1, $A1, A$1, A1  (optionally qualified by sheet)
_CELL_REF_RE = re.compile(
    r"(?P<col_abs>\$)?(?P<col>[A-Z]{1,3})(?P<row_abs>\$)?(?P<row>[0-9]+)"
)

# Full single-cell or range reference captured greedily inside a formula.
# Matches optional sheet prefix, then two cell refs optionally separated by ":".
_A1_REF_RE = re.compile(
    r"(?:(?P<sheet>[A-Za-z0-9_ ]+)!)?"
    r"(?P<start_col_abs>\$)?(?P<start_col>[A-Z]{1,3})(?P<start_row_abs>\$)?(?P<start_row>[0-9]+)"
    r"(?::"
    r"(?P<end_col_abs>\$)?(?P<end_col>[A-Z]{1,3})(?P<end_row_abs>\$)?(?P<end_row>[0-9]+)"
    r")?"
)


class _Ref(NamedTuple):
    """Parsed cell or range reference."""

    span: tuple[int, int]  # (start, end) positions in the formula string
    sheet: str | None      # optional sheet qualifier (kept verbatim when present)
    raw: str               # the original matched text


def expand_shared_formulas(
    cells: list,  # list of dicts with ref, formula, si, t, etc.
) -> None:
    """Resolve shared formula ``si`` references in-place.

    *cells* must include at least ``ref``, ``si`` (shared index), and
    ``formula`` (the raw formula text for the master) fields.  Master
    cells also need ``shared_ref`` (the range from ``<f ref=…>``).
    After the call every cell in a shared group has its own expanded
    ``formula`` field.
    """
    # Group cells by si index
    groups: dict[str, list[dict]] = {}
    for c in cells:
        si = c.get("si")
        if si is not None:
            groups.setdefault(si, []).append(c)

    for group in groups.values():
        master = next((c for c in group if c.get("shared_ref")), None)
        if master is None:
            continue
        slaves = [c for c in group if c is not master]
        if not slaves:
            continue

        # Parse master cell position
        m_col, m_row = _col_row(master["ref"])
        formula_text = master.get("formula", "")
        if not formula_text:
            for s in slaves:
                s["formula"] = ""
            continue

        for slave in slaves:
            s_col, s_row = _col_row(slave["ref"])
            dc = s_col - m_col
            dr = s_row - m_row
            slave["formula"] = _offset_formula(formula_text, dc, dr)


def _col_row(ref: str) -> tuple[int, int]:
    """Parse A1-style reference into (col, row)."""
    m = _CELL_REF_RE.match(ref.replace("$", ""))
    if not m:
        return 0, 0
    col_str = m.group("col")
    col = 0
    for ch in col_str:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return col, int(m.group("row"))


def _offset_formula(formula: str, dc: int, dr: int) -> str:
    """Apply row/column offset to every A1-style reference in *formula*."""
    if dc == 0 and dr == 0:
        return formula

    refs: list[_Ref] = []
    for m in _A1_REF_RE.finditer(formula):
        refs.append(_Ref(
            span=(m.start(), m.end()),
            sheet=m.group("sheet"),
            raw=m.group(0),
        ))

    if not refs:
        return formula

    parts: list[str] = []
    pos = 0
    for r in refs:
        # Keep text between references verbatim
        parts.append(formula[pos : r.span[0]])
        pos = r.span[1]

        if r.sheet is not None:
            # Cross-sheet references are kept as-is
            parts.append(r.raw)
            continue

        # Re-parse this specific match to get offset groups
        m = _A1_REF_RE.match(r.raw)
        if m is None:
            parts.append(r.raw)
            continue

        start_col_abs = m.group("start_col_abs") is not None
        start_row_abs = m.group("start_row_abs") is not None
        end_col = m.group("end_col")

        new_start = _offset_one_ref(
            col_abs=start_col_abs,
            row_abs=start_row_abs,
            col_str=m.group("start_col"),
            row_str=m.group("start_row"),
            dc=dc,
            dr=dr,
        )

        if end_col is None:
            parts.append(new_start)
        else:
            end_col_abs = m.group("end_col_abs") is not None
            end_row_abs = m.group("end_row_abs") is not None
            new_end = _offset_one_ref(
                col_abs=end_col_abs,
                row_abs=end_row_abs,
                col_str=end_col,
                row_str=m.group("end_row"),
                dc=dc,
                dr=dr,
            )
            parts.append(f"{new_start}:{new_end}")

    parts.append(formula[pos:])
    return "".join(parts)


def _offset_one_ref(
    col_abs: bool,
    row_abs: bool,
    col_str: str,
    row_str: str,
    dc: int,
    dr: int,
) -> str:
    """Apply offset to a single cell reference, respecting absolute anchors."""
    c = _col_from_str(col_str)
    r = int(row_str)
    if not col_abs:
        c += dc
    if not row_abs:
        r += dr
    col_frag = _str_from_col(c)
    row_frag = str(r)
    return f"{'$' if col_abs else ''}{col_frag}{'$' if row_abs else ''}{row_frag}"


def _col_from_str(s: str) -> int:
    c = 0
    for ch in s:
        c = c * 26 + (ord(ch) - ord("A") + 1)
    return c


def _str_from_col(c: int) -> str:
    result = ""
    while c > 0:
        c, rem = divmod(c - 1, 26)
        result = chr(ord("A") + rem) + result
    return result
