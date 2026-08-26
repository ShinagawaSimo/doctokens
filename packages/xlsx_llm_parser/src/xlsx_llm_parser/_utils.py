"""Shared spreadsheet utilities — A1 reference parsing and column conversion.

These are used across parser, renderer, and formula expansion modules.
"""




_COORD_SHIFT = 15  # Excel's maximum column index (16,384) fits in 15 bits.


def parse_ref(ref: str) -> tuple[int, int]:
    """Parse an A1-style reference into (col, row) as 1-based integers."""
    index = 0
    col = 0
    length = len(ref)
    while index < length:
        code = ord(ref[index])
        if 65 <= code <= 90:  # A-Z
            col = col * 26 + code - 64
        elif 97 <= code <= 122:  # a-z
            col = col * 26 + code - 96
        else:
            break
        index += 1
    row = int(ref[index:]) if index < length else 0
    return col, row


def col_letter(col: int) -> str:
    """Convert 1-based column number to A-Z letter(s)."""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def coord_key(col: int, row: int) -> int:
    """Encode one 1-based cell coordinate as a compact integer map key."""
    return (row << _COORD_SHIFT) | col


def _col_from_str(s: str) -> int:
    """Convert A-Z column letter(s) to 1-based column number."""
    c = 0
    for ch in s:
        c = c * 26 + (ord(ch) - ord("A") + 1)
    return c
