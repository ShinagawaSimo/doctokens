"""OOXML number-format tables, tokenization, and display formatting."""

from __future__ import annotations

import math
import re
from decimal import Decimal

from .number_formats.codes import _date_scan_text, _localized_builtin_code
from .number_formats.codes import builtin_format_code as builtin_format_code
from .number_formats.codes import resolve_format as resolve_format
from .number_formats.dates import _format_date_value
from .number_formats.numbers import _format_number_value
from .number_formats.sections import _clean_display_pattern, _section_directives, _select_format_section, _split_format_sections


def format_value(
    num_fmt_id: int,
    fmt_code: str,
    raw: str,
    *,
    date_1904: bool,
    locale: str,
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
    section, _value = _select_format_section(num, fmt_code)
    if section is None:
        return raw
    if _section_directives(section)[2]:
        # DBNum is a numbering system, not a digit substitution. Keep the
        # saved value until the target Excel variants have real coverage.
        return raw
    is_date, _is_pct = resolve_format(0, section, locale)
    try:
        if is_date:
            return _format_date_value(num, section, date_1904, locale)
        return _format_number_value(num, raw, fmt_code, _is_pct, locale)
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


def formula_bar_value(raw: str, fmt_code: str, locale: str) -> str | None:
    """Reconstruct only the verified-independent, ordinary numeric edit form.

    The formula bar is an application rendering, not the lexical XML value.
    Date/time, percentage, locale-specific or precision-sensitive edit forms
    need a separate Excel comparison; returning None never substitutes a
    serial or cached result for that unavailable rendering.
    """
    if locale.replace("_", "-").lower() not in {"zh-cn", "en-us"} or not fmt_code:
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite():
            return None
        section, _selected = _select_format_section(float(value), fmt_code)
        if section is None:
            return None
        is_date, is_pct = resolve_format(0, section, locale)
        if is_date or is_pct or _section_directives(section)[2]:
            return None
        syntax = _date_scan_text(section)
        if re.search(r"(?i)[a-z]", syntax) and syntax.lower() != "general":
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


def number_format_color(raw: str, fmt_code: str, *, is_text: bool = False) -> str | None:
    """Resolve named section colors independently of font-table styles."""
    if is_text:
        sections = _split_format_sections(fmt_code)
        section = sections[3] if len(sections) == 4 else sections[0] if "@" in _date_scan_text(fmt_code) else None
    else:
        try:
            value = float(raw)
            if not math.isfinite(value):
                return None
            section, _selected = _select_format_section(value, fmt_code)
        except ValueError:
            return None
    if section is None:
        return None
    match = next(
        (
            directive
            for directive in re.finditer(r"\[([^\]]*)\]", section)
            if directive.group(1).lower() in {"black", "blue", "cyan", "green", "magenta", "red", "white", "yellow"}
        ),
        None,
    )
    colors = {
        "black": "#000000",
        "blue": "#0000FF",
        "cyan": "#00FFFF",
        "green": "#008000",
        "magenta": "#FF00FF",
        "red": "#FF0000",
        "white": "#FFFFFF",
        "yellow": "#FFFF00",
    }
    return colors.get(match.group(1).lower()) if match else None


__all__ = [
    "builtin_format_code",
    "format_value",
    "formula_bar_value",
    "number_format_color",
    "resolve_format",
    "text_format_parts",
]
