"""OOXML number-format tables, tokenization, and display formatting."""

from __future__ import annotations

import math
import re
from decimal import Decimal

from .number_formats.chinese import format_chinese_integer
from .number_formats.codes import _date_scan_text, _localized_builtin_code
from .number_formats.codes import builtin_format_code as builtin_format_code
from .number_formats.codes import resolve_format as resolve_format
from .number_formats.dates import _format_date_value, time_formula_bar_value
from .number_formats.numbers import _format_number_value
from .number_formats.program import FormatProgram
from .number_formats.sections import _clean_display_pattern, _split_format_sections


def format_value(
    num_fmt_id: int,
    fmt_code: str,
    raw: str,
    *,
    date_1904: bool,
    locale: str,
    _program: FormatProgram | None = None,
) -> str:
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return raw
    if not math.isfinite(num):
        return raw
    fmt_code = fmt_code or _localized_builtin_code(num_fmt_id, locale)
    if not fmt_code or fmt_code.lower() == "general":
        return raw
    program = _program or FormatProgram(fmt_code, locale)
    section, _value = program.select(num)
    if section is None:
        return raw
    is_date, _is_pct = program.classify(section)
    try:
        if is_date:
            return _format_date_value(num, section, date_1904, locale, context=program.date(section))
        if program.section_directives(section).dbnum:
            rendered = format_chinese_integer(Decimal(raw), section, fmt_code, locale)
            return rendered if rendered is not None else raw
        return _format_number_value(num, raw, fmt_code, _is_pct, locale, program=program)
    except (ArithmeticError, ValueError):
        return raw


def text_format_parts(fmt_code: str) -> list[str | None] | None:
    """Return literals and text insertion points; None means no text section."""
    sections = _split_format_sections(fmt_code)
    if len(sections) == 4:
        section = sections[3]
    elif len(sections) == 1 and "@" in _date_scan_text(fmt_code):
        section = fmt_code
    else:
        return None
    syntax = _date_scan_text(section)
    result: list[str | None] = []
    start = 0
    for match in re.finditer("@", syntax):
        result.extend((_clean_display_pattern(section[start : match.start()]), None))
        start = match.end()
    result.append(_clean_display_pattern(section[start:]))
    return result


def formula_bar_value(raw: str, fmt_code: str, locale: str, *, _program: FormatProgram | None = None) -> str | None:
    """Reconstruct supported numeric and Simplified Chinese time edit forms.

    The formula bar is an application rendering, not the lexical XML value.
    Unverified date/time, percentage or precision-sensitive edit forms
    need a separate Excel comparison; returning None never substitutes a
    serial or cached result for that unavailable rendering.
    """
    if locale.replace("_", "-").lower() not in {"zh-cn", "en-us"} or not fmt_code:
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite():
            return None
        program = _program or FormatProgram(fmt_code, locale)
        section, _selected = program.select(float(value))
        if section is None:
            return None
        is_date, is_pct = program.classify(section)
        if is_date:
            return time_formula_bar_value(value, section, locale)
        if is_pct:
            return None
        if program.section_directives(section).dbnum and format_chinese_integer(value, section, fmt_code, locale) is None:
            return None
        syntax = program.syntax(section)
        # Scientific display formats use the uppercase ``E+``/``E-`` token.
        # It is formatting syntax, not literal text, so it must not prevent
        # recovery of the ordinary saved number shown in Excel's formula bar.
        syntax_without_scientific = re.sub(r"[0#?]+(?:\.[0#?]+)?E[+-][0#?]+", "", syntax)
        if re.search(r"(?i)[a-z]", syntax_without_scientific) and syntax.strip().lower() != "general":
            return None
        if abs(value) >= Decimal("1e15") or 0 < abs(value) < Decimal("1e-9"):
            return None
        if len(value.normalize().as_tuple().digits) > 15:
            return None
        if value == 0:
            return "0"
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    except (ArithmeticError, ValueError):
        return None


def number_format_color(raw: str, fmt_code: str, *, is_text: bool = False, _program: FormatProgram | None = None) -> str | None:
    """Resolve named section colors independently of font-table styles."""
    program = _program or FormatProgram(fmt_code, "zh-CN")
    if not any(program.colors.values()):
        return None
    if is_text:
        sections = program.sections
        section = sections[3] if len(sections) == 4 else sections[0] if "@" in _date_scan_text(fmt_code) else None
    else:
        try:
            value = float(raw)
            if not math.isfinite(value):
                return None
            section, _selected = program.select(value)
        except ValueError:
            return None
    if section is None:
        return None
    return program.colors[section]


__all__ = [
    "builtin_format_code",
    "format_value",
    "formula_bar_value",
    "number_format_color",
    "resolve_format",
    "text_format_parts",
]
