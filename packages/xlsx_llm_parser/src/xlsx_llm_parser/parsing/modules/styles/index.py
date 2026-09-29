"""Runtime style index used while rendering worksheet cells.

The XML reader lives in :mod:`styles.parser`; number-format rendering lives in
:mod:`styles.number_format`; and theme/font/fill records live in
:mod:`styles.records`. Keeping this module focused on the in-memory index
prevents new format cases from making the public style object unmanageably
large while preserving the historical ``styles.index`` import path.
"""

from __future__ import annotations

from ....models import CellControl
from .number_format import format_value as format_number_value
from .number_format import formula_bar_value, number_format_color, resolve_format, text_format_parts
from .records import FillInfo, FontInfo


class FormatIndex:
    """Cell-to-format and semantic-style resolver built from ``styles.xml``."""

    def __init__(self, *, locale: str = "zh-CN") -> None:
        # cellXfs index → (numFmtId, formatCode, fontId, fillId, locked, formulaHidden)
        self._cell_formats: list[tuple[int, str, int, int, bool, bool]] = []
        # (locale, numFmtId, formatCode) → (is_date, is_pct)
        self._fmt_cache: dict[tuple[str, int, str], tuple[bool, bool]] = {}
        # style_index → resolved attribute string ("" = no styles)
        self._style_attrs_cache: dict[int, str] = {}
        self._fonts: list[FontInfo] = []
        self._fills: list[FillInfo] = []
        # dxf index → compact semantic style summary used by conditional formatting.
        self._differential_styles: list[str] = []
        self._cell_controls: dict[int, CellControl] = {}
        self.date_1904 = False
        self.locale = locale

    def set_date_system(self, date_1904: bool) -> None:
        self.date_1904 = date_1904

    def set_locale(self, locale: str) -> None:
        """Set the workbook/UI locale used for localized built-in formats."""
        if locale:
            self.locale = locale
            self._fmt_cache.clear()

    def register_font(self, font_info: FontInfo) -> None:
        self._fonts.append(font_info)

    def register_fill(self, fill_info: FillInfo) -> None:
        self._fills.append(fill_info)

    def register_differential_style(self, style: str) -> None:
        self._differential_styles.append(style)

    def differential_style(self, dxf_id: int) -> str:
        """Return the meaningful formatting carried by a conditional-format dxf."""
        if 0 <= dxf_id < len(self._differential_styles):
            return self._differential_styles[dxf_id]
        return ""

    def set_cell_controls(self, controls: dict[int, CellControl]) -> None:
        """Attach feature-property controls resolved for cell-XF indices."""
        self._cell_controls = controls

    def cell_control(self, style_index: int | None) -> CellControl | None:
        if style_index is None:
            return None
        return self._cell_controls.get(style_index)

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

    def format_value(self, style_index: int | None, raw: str, *, locale: str | None = None) -> str:
        """Apply the resolved number format to a raw cell value string."""
        if style_index is None or not 0 <= style_index < len(self._cell_formats):
            return raw
        num_fmt_id, fmt_code, _font_id, _fill_id, _locked, _hidden = self._cell_formats[style_index]
        return format_number_value(
            num_fmt_id,
            fmt_code,
            raw,
            date_1904=self.date_1904,
            locale=locale or self.locale,
        )

    def format_code(self, style_index: int | None) -> str:
        if style_index is None:
            return "General"
        if 0 <= style_index < len(self._cell_formats):
            return self._cell_formats[style_index][1]
        return ""

    def text_format_parts(self, style_index: int | None) -> list[str | None] | None:
        return text_format_parts(self.format_code(style_index))

    def formula_bar_value(self, style_index: int | None, value: str) -> str | None:
        return formula_bar_value(value, self.format_code(style_index), self.locale)

    def number_format_color(self, style_index: int | None, value: str, *, is_text: bool = False) -> str | None:
        return number_format_color(value, self.format_code(style_index), is_text=is_text)

    def style_attrs(self, style_index: int | None) -> str:
        """Return semantic font/fill attributes for a cell."""
        if style_index is None or style_index >= len(self._cell_formats):
            return ""
        if style_index not in self._style_attrs_cache:
            _num_fmt_id, _fmt_code, font_id, fill_id, _locked, _hidden = self._cell_formats[style_index]
            parts: list[str] = []
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
        """Return non-default protection attributes for a cell style."""
        if style_index is None or style_index >= len(self._cell_formats):
            return ""
        _num_fmt_id, _fmt_code, _font_id, _fill_id, locked, formula_hidden = self._cell_formats[style_index]
        parts: list[str] = []
        if not locked:
            parts.append("unlocked")
        if formula_hidden:
            parts.append("formulaHidden")
        return " ".join(parts)

    def _resolve(self, num_fmt_id: int, fmt_code: str, locale: str) -> tuple[bool, bool]:
        key = (locale, num_fmt_id, fmt_code)
        if key not in self._fmt_cache:
            self._fmt_cache[key] = resolve_format(num_fmt_id, fmt_code, locale)
        return self._fmt_cache[key]


# Compatibility re-export: existing callers historically imported parse_styles
# from styles.index. The implementation is intentionally kept in parser.py.
from .parser import StyleDetail, parse_styles  # noqa: E402  (after FormatIndex)

__all__ = ["FormatIndex", "StyleDetail", "parse_styles"]
