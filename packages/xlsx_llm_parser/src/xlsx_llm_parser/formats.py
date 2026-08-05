"""Number format detection and date-serial decoding.

Parses xl/styles.xml to build a cell→format index, then decodes
date serials, percentages, and currency values from raw cell data.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageReader

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# numFmtId ranges for built-in date / time formats (ECMA-376 §18.8.30).
_BUILTIN_DATE_IDS: set[int] = set()
for _lo, _hi in [
    (14, 22), (27, 36), (45, 47), (50, 58), (71, 81),
]:
    _BUILTIN_DATE_IDS.update(range(_lo, _hi + 1))

# Built-in percentage format IDs.
_BUILTIN_PCT_IDS = {9, 10}

# Tokens that indicate a custom format string encodes a date or time.
_DATE_TOKENS_RE = re.compile(
    r"[yYmMdDhHsS]|AM/PM|am/pm|A/P|a/p|\[h\]|\[m\]|\[s\]",
)

# Percentage marker.
_PCT_RE = re.compile(r"%")

# ── Public API ──


class FormatIndex:
    """Cell → display-value resolver built from styles.xml."""

    def __init__(self) -> None:
        # cellXfs index → (numFmtId, formatCode)
        self._cell_formats: list[tuple[int, str]] = []
        # numFmtId → (is_date, is_pct)
        self._fmt_cache: dict[int, tuple[bool, bool]] = {}
        self.date_1904 = False

    def set_date_system(self, date_1904: bool) -> None:
        self.date_1904 = date_1904

    def register_cell_format(self, num_fmt_id: int, format_code: str) -> None:
        self._cell_formats.append((num_fmt_id, format_code))

    def format_value(self, style_index: int | None, raw: str) -> str:
        """Apply number formatting to a raw cell value string."""
        if style_index is None or style_index >= len(self._cell_formats):
            return raw
        try:
            num = float(raw)
        except ValueError:
            return raw

        num_fmt_id, fmt_code = self._cell_formats[style_index]
        is_date, is_pct = self._resolve(num_fmt_id, fmt_code)

        if is_date:
            return _decode_date(num, self.date_1904)
        if is_pct:
            return f"{num * 100:g}%"
        return raw

    def _resolve(self, num_fmt_id: int, fmt_code: str) -> tuple[bool, bool]:
        if num_fmt_id not in self._fmt_cache:
            is_date = num_fmt_id in _BUILTIN_DATE_IDS or bool(
                _DATE_TOKENS_RE.search(fmt_code)
            )
            is_pct = num_fmt_id in _BUILTIN_PCT_IDS or bool(
                _PCT_RE.search(fmt_code)
            )
            self._fmt_cache[num_fmt_id] = (is_date, is_pct)
        return self._fmt_cache[num_fmt_id]


def parse_styles(pkg: PackageReader) -> FormatIndex:
    """Parse xl/styles.xml and build a FormatIndex."""
    index = FormatIndex()

    if not pkg.exists("xl/styles.xml"):
        return index

    with pkg.open_entry("xl/styles.xml") as stream:
        root = ET.parse(stream).getroot()

    # Custom number formats: numFmtId → formatCode
    custom_fmts: dict[int, str] = {}
    num_fmts = root.find(f"{{{NS_S}}}numFmts")
    if num_fmts is not None:
        for nf in num_fmts.findall(f"{{{NS_S}}}numFmt"):
            fid = int(nf.get("numFmtId", "0"))
            code = nf.get("formatCode", "")
            custom_fmts[fid] = code

    # Cell formats: each references a numFmtId
    cell_xfs = root.find(f"{{{NS_S}}}cellXfs")
    if cell_xfs is not None:
        for xf in cell_xfs.findall(f"{{{NS_S}}}xf"):
            fid = int(xf.get("numFmtId", "0"))
            code = custom_fmts.get(fid, "")
            index.register_cell_format(fid, code)

    return index


def _decode_date(serial: float, date_1904: bool) -> str:
    """Decode an Excel date serial number to ISO 8601.

    1900 system: epoch is 1899-12-31, serial 1 = 1900-01-01.
    The Lotus 1-2-3 compatibility bug treats 1900 as a leap year:
    serial 60 = 1900-02-29 (spurious), compensated by subtracting 1
    from serials >= 61.
    """
    if date_1904:
        return (datetime(1904, 1, 1) + timedelta(days=int(serial))).date().isoformat()

    if serial <= 0:
        return str(serial)
    ordinal = int(serial)
    if ordinal == 60:
        return "1900-02-29"  # the spurious leap day
    if ordinal > 60:
        ordinal -= 1
    return (datetime(1899, 12, 31) + timedelta(days=ordinal)).date().isoformat()
