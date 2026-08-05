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
    """Cell → display-value and style resolver built from styles.xml."""

    def __init__(self) -> None:
        # cellXfs index → (numFmtId, formatCode, fontId, fillId)
        self._cell_formats: list[tuple[int, str, int, int]] = []
        # numFmtId → (is_date, is_pct)
        self._fmt_cache: dict[int, tuple[bool, bool]] = {}
        # style_index → resolved attribute string ("" = no styles)
        self._style_attrs_cache: dict[int, str] = {}
        # fontId → {"bold": bool, "italic": bool, "color": str | None}
        self._fonts: list[dict] = []
        # fillId → {"fill": str | None}
        self._fills: list[dict] = []
        self.date_1904 = False

    def set_date_system(self, date_1904: bool) -> None:
        self.date_1904 = date_1904

    def register_font(self, font_info: dict) -> None:
        self._fonts.append(font_info)

    def register_fill(self, fill_info: dict) -> None:
        self._fills.append(fill_info)

    def register_cell_format(self, num_fmt_id: int, format_code: str,
                             font_id: int = 0, fill_id: int = 0) -> None:
        self._cell_formats.append((num_fmt_id, format_code, font_id, fill_id))

    def format_value(self, style_index: int | None, raw: str) -> str:
        """Apply number formatting to a raw cell value string."""
        if style_index is None or style_index >= len(self._cell_formats):
            return raw
        try:
            num = float(raw)
        except ValueError:
            return raw

        num_fmt_id, fmt_code, _font_id, _fill_id = self._cell_formats[style_index]
        is_date, is_pct = self._resolve(num_fmt_id, fmt_code)

        if is_date:
            return _decode_date(num, self.date_1904)
        if is_pct:
            return f"{num * 100:g}%"
        return raw

    def style_attrs(self, style_index: int | None) -> str:
        """Return semantic style attributes for a cell, or empty string."""
        if style_index is None or style_index >= len(self._cell_formats):
            return ""
        if style_index not in self._style_attrs_cache:
            _num_fmt_id, _fmt_code, font_id, fill_id = self._cell_formats[style_index]
            parts = []
            if font_id < len(self._fonts):
                font = self._fonts[font_id]
                if font.get("bold"):
                    parts.append("bold")
                if font.get("italic"):
                    parts.append("italic")
                if font.get("underline"):
                    parts.append("underline")
                if font.get("color"):
                    parts.append(f"color={font['color']}")
            if fill_id < len(self._fills):
                fill = self._fills[fill_id]
                if fill.get("fill"):
                    parts.append(f"fill={fill['fill']}")
            self._style_attrs_cache[style_index] = " ".join(parts)
        return self._style_attrs_cache[style_index]

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

    # Fonts: indexed by position
    fonts_elem = root.find(f"{{{NS_S}}}fonts")
    if fonts_elem is not None:
        for font in fonts_elem.findall(f"{{{NS_S}}}font"):
            info: dict = {"bold": False, "italic": False, "underline": False}
            if font.find(f"{{{NS_S}}}b") is not None:
                info["bold"] = True
            if font.find(f"{{{NS_S}}}i") is not None:
                info["italic"] = True
            if font.find(f"{{{NS_S}}}u") is not None:
                info["underline"] = True
            color = font.find(f"{{{NS_S}}}color")
            if color is not None:
                rgb = color.get("rgb")
                if rgb and rgb != "00000000":
                    info["color"] = f"#{_rgb_hex(rgb)}"
            index.register_font(info)

    # Fills: indexed by position
    fills_elem = root.find(f"{{{NS_S}}}fills")
    if fills_elem is not None:
        for fill in fills_elem.findall(f"{{{NS_S}}}fill"):
            fill_info: dict = {}
            pf = fill.find(f"{{{NS_S}}}patternFill")
            if pf is not None:
                fg = pf.find(f"{{{NS_S}}}fgColor")
                if fg is not None:
                    rgb = fg.get("rgb")
                    if rgb and rgb != "00000000":
                        fill_info["fill"] = f"#{_rgb_hex(rgb)}"
            index.register_fill(fill_info)

    # Cell formats: each references numFmtId, fontId, fillId
    cell_xfs = root.find(f"{{{NS_S}}}cellXfs")
    if cell_xfs is not None:
        for xf in cell_xfs.findall(f"{{{NS_S}}}xf"):
            fid = int(xf.get("numFmtId", "0"))
            font_id = int(xf.get("fontId", "0"))
            fill_id = int(xf.get("fillId", "0"))
            code = custom_fmts.get(fid, "")
            index.register_cell_format(fid, code, font_id, fill_id)

    return index


def _rgb_hex(rgb: str) -> str:
    """Normalize OOXML color (AARRGGBB or RRGGBB) to RRGGBB."""
    if len(rgb) == 8:
        return rgb[2:]  # strip alpha
    return rgb


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
