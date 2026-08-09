"""Number format detection and date-serial decoding.

Parses xl/styles.xml to build a cell→format index, then decodes
date serials, percentages, and currency values from raw cell data.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import TypedDict
from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageReader

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Spreadsheet theme color index order.
_THEME_SLOTS = [
    "lt1",
    "dk1",
    "lt2",
    "dk2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
]

# Office default theme colors (fallback when theme1.xml is absent).
_DEFAULT_THEME: dict[int, str] = dict(
    enumerate(
        [
            "FFFFFF",
            "000000",
            "E7E6E6",
            "44546A",
            "4472C4",
            "ED7D31",
            "A5A5A5",
            "FFC000",
            "5B9BD5",
            "70AD47",
            "0563C1",
            "954F72",
        ]
    )
)

# numFmtId ranges for built-in date / time formats (ECMA-376 §18.8.30).
_BUILTIN_DATE_IDS: set[int] = set()
for _lo, _hi in [
    (14, 22),
    (27, 36),
    (45, 47),
    (50, 58),
    (71, 81),
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


class FontInfo(TypedDict, total=False):
    bold: bool
    italic: bool
    underline: bool
    color: str


class FillInfo(TypedDict, total=False):
    fill: str


class FormatIndex:
    """Cell → display-value and style resolver built from styles.xml."""

    def __init__(self) -> None:
        # cellXfs index → (numFmtId, formatCode, fontId, fillId, locked, formulaHidden)
        self._cell_formats: list[tuple[int, str, int, int, bool, bool]] = []
        # numFmtId → (is_date, is_pct)
        self._fmt_cache: dict[int, tuple[bool, bool]] = {}
        # style_index → resolved attribute string ("" = no styles)
        self._style_attrs_cache: dict[int, str] = {}
        # fontId → {"bold": bool, "italic": bool, "color": str | None}
        self._fonts: list[FontInfo] = []
        # fillId → {"fill": str | None}
        self._fills: list[FillInfo] = []
        self.date_1904 = False

    def set_date_system(self, date_1904: bool) -> None:
        self.date_1904 = date_1904

    def register_font(self, font_info: FontInfo) -> None:
        self._fonts.append(font_info)

    def register_fill(self, fill_info: FillInfo) -> None:
        self._fills.append(fill_info)

    def register_cell_format(
        self,
        num_fmt_id: int,
        format_code: str,
        font_id: int = 0,
        fill_id: int = 0,
        locked: bool = True,
        formula_hidden: bool = False,
    ) -> None:
        self._cell_formats.append((num_fmt_id, format_code, font_id, fill_id, locked, formula_hidden))

    def format_value(self, style_index: int | None, raw: str) -> str:
        """Apply number formatting to a raw cell value string."""
        if style_index is None or style_index >= len(self._cell_formats):
            return raw
        try:
            num = float(raw)
        except ValueError:
            return raw

        num_fmt_id, fmt_code, _font_id, _fill_id, _locked, _hidden = self._cell_formats[style_index]
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
            _num_fmt_id, _fmt_code, font_id, fill_id, _locked, _hidden = self._cell_formats[style_index]
            parts = []
            if font_id < len(self._fonts):
                font = self._fonts[font_id]
                if font.get("bold"):
                    parts.append("bold")
                if font.get("italic"):
                    parts.append("italic")
                if font.get("underline"):
                    parts.append("underline")
                color = font.get("color")
                if color and color.upper() != "#000000":
                    parts.append(f"color={color}")
            if fill_id < len(self._fills):
                fill = self._fills[fill_id]
                if fill.get("fill"):
                    parts.append(f"fill={fill['fill']}")
            self._style_attrs_cache[style_index] = " ".join(parts)
        return self._style_attrs_cache[style_index]

    def protection_attrs(self, style_index: int | None) -> str:
        """Return protection-related attributes (''unlocked'' / ''formulaHidden'')
        when the cell deviates from the Excel default (locked, formula visible).

        Only meaningful when sheet protection is active; callers must check that
        separately.
        """
        if style_index is None or style_index >= len(self._cell_formats):
            return ""
        _num_fmt_id, _fmt_code, _font_id, _fill_id, locked, formula_hidden = self._cell_formats[style_index]
        parts = []
        if not locked:
            parts.append("unlocked")
        if formula_hidden:
            parts.append("formulaHidden")
        return " ".join(parts)

    def _resolve(self, num_fmt_id: int, fmt_code: str) -> tuple[bool, bool]:
        if num_fmt_id not in self._fmt_cache:
            is_date = num_fmt_id in _BUILTIN_DATE_IDS or bool(_DATE_TOKENS_RE.search(fmt_code))
            is_pct = num_fmt_id in _BUILTIN_PCT_IDS or bool(_PCT_RE.search(fmt_code))
            self._fmt_cache[num_fmt_id] = (is_date, is_pct)
        return self._fmt_cache[num_fmt_id]


def parse_styles(pkg: PackageReader) -> FormatIndex:
    """Parse xl/styles.xml and build a FormatIndex."""
    index = FormatIndex()

    if not pkg.exists("xl/styles.xml"):
        return index

    # Resolve theme colors so that theme="N" can be mapped to RGB.
    theme = _parse_theme(pkg)

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
            info: FontInfo = {"bold": False, "italic": False, "underline": False}
            if font.find(f"{{{NS_S}}}b") is not None:
                info["bold"] = True
            if font.find(f"{{{NS_S}}}i") is not None:
                info["italic"] = True
            if font.find(f"{{{NS_S}}}u") is not None:
                info["underline"] = True
            color = font.find(f"{{{NS_S}}}color")
            if color is not None:
                resolved = _resolve_color(color, theme)
                if resolved:
                    info["color"] = f"#{resolved}"
            index.register_font(info)

    # Fills: indexed by position
    fills_elem = root.find(f"{{{NS_S}}}fills")
    if fills_elem is not None:
        for fill in fills_elem.findall(f"{{{NS_S}}}fill"):
            fill_info: FillInfo = {}
            pf = fill.find(f"{{{NS_S}}}patternFill")
            if pf is not None:
                fg = pf.find(f"{{{NS_S}}}fgColor")
                if fg is not None:
                    resolved = _resolve_color(fg, theme)
                    if resolved:
                        fill_info["fill"] = f"#{resolved}"
            index.register_fill(fill_info)

    # Cell formats: each references numFmtId, fontId, fillId
    cell_xfs = root.find(f"{{{NS_S}}}cellXfs")
    if cell_xfs is not None:
        for xf in cell_xfs.findall(f"{{{NS_S}}}xf"):
            fid = int(xf.get("numFmtId", "0"))
            font_id = int(xf.get("fontId", "0"))
            fill_id = int(xf.get("fillId", "0"))
            code = custom_fmts.get(fid, "")
            locked = True
            formula_hidden = False
            protection = xf.find(f"{{{NS_S}}}protection")
            if protection is not None:
                if protection.get("locked") == "0":
                    locked = False
                if protection.get("hidden") == "1":
                    formula_hidden = True
            index.register_cell_format(fid, code, font_id, fill_id, locked, formula_hidden)

    return index


def _rgb_hex(rgb: str) -> str:
    """Normalize OOXML color (AARRGGBB or RRGGBB) to RRGGBB."""
    if len(rgb) == 8:
        return rgb[2:]  # strip alpha
    return rgb


def _parse_theme(pkg: PackageReader) -> dict[int, str]:
    """Parse xl/theme/theme1.xml into index → RRGGBB hex mapping.

    Returns the Office default theme when the part is missing.
    """
    if not pkg.exists("xl/theme/theme1.xml"):
        return _DEFAULT_THEME.copy()

    with pkg.open_entry("xl/theme/theme1.xml") as stream:
        root = ET.parse(stream).getroot()

    scheme = root.find(f"{{{NS_A}}}themeElements/{{{NS_A}}}clrScheme")
    if scheme is None:
        return _DEFAULT_THEME.copy()

    mapping: dict[int, str] = {}
    for idx, slot in enumerate(_THEME_SLOTS):
        elem = scheme.find(f"{{{NS_A}}}{slot}")
        resolved = _theme_slot_value(elem)
        if resolved:
            mapping[idx] = resolved
            continue
        mapping[idx] = _DEFAULT_THEME.get(idx, "000000")
    return mapping


def _theme_slot_value(elem: ET.Element | None) -> str | None:
    if elem is None:
        return None
    srgb = elem.find(f"{{{NS_A}}}srgbClr")
    if srgb is not None:
        val = srgb.get("val", "")
        if val:
            return val
    sys_color = elem.find(f"{{{NS_A}}}sysClr")
    if sys_color is not None:
        val = sys_color.get("lastClr", "")
        if val:
            return val
    return None


def _resolve_color(color_elem: ET.Element, theme: dict[int, str]) -> str | None:
    """Extract a RRGGBB hex string from an OOXML <color> element.

    Handles ``rgb`` attribute (explicit), ``theme`` attribute (resolved
    against the current theme), and optional ``tint`` for light/dark
    variations.
    """
    # Explicit RGB — the common case; black placeholder is skipped.
    rgb = color_elem.get("rgb")
    if rgb and rgb != "00000000":
        return _rgb_hex(rgb)

    # Theme color reference
    theme_str = color_elem.get("theme")
    if theme_str is not None:
        try:
            idx = int(theme_str)
            base = theme.get(idx)
            if base is None:
                return None
            tint_str = color_elem.get("tint")
            if tint_str is not None:
                try:
                    return _apply_tint(base, float(tint_str))
                except ValueError:
                    pass
            return base
        except ValueError:
            pass

    return None


def _apply_tint(rgb_hex: str, tint: float) -> str:
    """Mix an OOXML tint value into a RRGGBB hex colour.

    Negative *tint* darkens (moves toward black), positive *tint* lightens
    (moves toward white).  The linear interpolation is defined in
    ECMA-376 §20.1.2.3.29.
    """
    if tint == 0:
        return rgb_hex

    channels = (int(rgb_hex[i : i + 2], 16) for i in (0, 2, 4))
    if tint < 0:
        factor = 1 + tint  # tint is negative → darken
        result = (max(0, min(255, int(c * factor))) for c in channels)
    else:
        # tint > 0 → lighten toward white
        result = (max(0, min(255, int(c * (1 - tint) + 255 * tint))) for c in channels)
    return "".join(f"{c:02X}" for c in result)


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
