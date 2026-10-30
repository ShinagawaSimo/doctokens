"""Runtime style index used while rendering worksheet cells.

The XML reader lives in :mod:`styles.parser`; number-format rendering lives in
:mod:`doctokens_excel.formatting.values`; and theme/font/fill records live in
:mod:`styles.records`. Keeping this module focused on the in-memory index
prevents new format cases from making the public style object unmanageably
large.
"""

from __future__ import annotations

from doctokens_excel.formatting.program import FormatProgram
from doctokens_excel.formatting.values import (
    builtin_format_code,
    formula_bar_value,
    number_format_color,
    text_format_parts,
)
from doctokens_excel.formatting.values import format_value as format_number_value

from ....model.workbook import CellControl
from .records import FillInfo, FontInfo


class FormatIndex:
    """Cell-to-format and semantic-style resolver built from ``styles.xml``."""

    def __init__(self, *, locale: str = "zh-CN") -> None:
        # cellXfs index → (numFmtId, formatCode, fontId, fillId, locked, formulaHidden)
        self._cell_formats: list[tuple[int, str, int, int, bool, bool]] = []
        self._programs: dict[tuple[str, str], FormatProgram] = {}
        self._text_parts: dict[str, list[str | None] | None] = {}
        # style_index → resolved attribute string ("" = no styles)
        self._style_attrs_cache: dict[int, str] = {}
        self._fonts: list[FontInfo] = []
        self._fills: list[FillInfo] = []
        # dxf index → compact semantic style summary used by conditional formatting.
        self._differential_styles: list[str] = []
        self._cell_controls: dict[int, CellControl] = {}
        self._visible_blank_styles: set[int] = set()
        self.date_1904 = False
        self.locale = locale

    def set_date_system(self, date_1904: bool) -> None:
        self.date_1904 = date_1904

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
        visible_blank: bool = False,
    ) -> None:
        if visible_blank or not locked or formula_hidden:
            self._visible_blank_styles.add(len(self._cell_formats))
        self._cell_formats.append((num_fmt_id, format_code, font_id, fill_id, locked, formula_hidden))

    def preserves_blank(self, style_index: int | None) -> bool:
        """Keep visible fills/borders and controls even in lower densities."""
        if style_index is None:
            return False
        if not 0 <= style_index < len(self._cell_formats):
            return True  # Unknown styling is not evidence of a disposable blank.
        return style_index in self._visible_blank_styles or style_index in self._cell_controls

    def format_value(self, style_index: int | None, raw: str, *, locale: str | None = None) -> str:
        """Apply the resolved number format to a raw cell value string."""
        if style_index is None or not 0 <= style_index < len(self._cell_formats):
            return raw
        num_fmt_id, fmt_code, _font_id, _fill_id, _locked, _hidden = self._cell_formats[style_index]
        effective_locale = locale or self.locale
        effective_code = fmt_code or builtin_format_code(num_fmt_id, effective_locale)
        return format_number_value(
            num_fmt_id,
            fmt_code,
            raw,
            date_1904=self.date_1904,
            locale=effective_locale,
            _program=self._program(effective_code, effective_locale),
        )

    def format_code(self, style_index: int | None) -> str:
        if style_index is None:
            return "General"
        if 0 <= style_index < len(self._cell_formats):
            return self._cell_formats[style_index][1]
        return ""

    def text_format_parts(self, style_index: int | None) -> list[str | None] | None:
        code = self.format_code(style_index)
        if code not in self._text_parts:
            self._text_parts[code] = text_format_parts(code)
        parts = self._text_parts[code]
        return list(parts) if parts is not None else None

    def formula_bar_value(self, style_index: int | None, value: str) -> str | None:
        code = self.format_code(style_index)
        return formula_bar_value(value, code, self.locale, _program=self._program(code, self.locale))

    def number_format_color(self, style_index: int | None, value: str, *, is_text: bool = False) -> str | None:
        code = self.format_code(style_index)
        return number_format_color(value, code, is_text=is_text, _program=self._program(code, self.locale))

    def _program(self, code: str, locale: str) -> FormatProgram:
        key = (locale, code)
        if key not in self._programs:
            self._programs[key] = FormatProgram(code, locale)
        return self._programs[key]

    def style_attrs(self, style_index: int | None) -> str:
        """Return semantic font/fill attributes for a cell."""
        if style_index is None or not 0 <= style_index < len(self._cell_formats):
            return ""
        if style_index not in self._style_attrs_cache:
            _num_fmt_id, _fmt_code, font_id, fill_id, _locked, _hidden = self._cell_formats[style_index]
            parts: list[str] = []
            if 0 <= font_id < len(self._fonts):
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
            if 0 <= fill_id < len(self._fills):
                fill = self._fills[fill_id]
                if fill.get("fill"):
                    parts.append(f"fill={fill['fill']}")
            self._style_attrs_cache[style_index] = " ".join(parts)
        return self._style_attrs_cache[style_index]

    def protection_attrs(self, style_index: int | None) -> str:
        """Return non-default protection attributes for a cell style."""
        if style_index is None or not 0 <= style_index < len(self._cell_formats):
            return ""
        _num_fmt_id, _fmt_code, _font_id, _fill_id, locked, formula_hidden = self._cell_formats[style_index]
        parts: list[str] = []
        if not locked:
            parts.append("unlocked")
        if formula_hidden:
            parts.append("formulaHidden")
        return " ".join(parts)


__all__ = ["FormatIndex"]
