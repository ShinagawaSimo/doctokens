"""Explicit supported display dispatch for legacy Excel saved numeric values."""

from __future__ import annotations

import math
import re
from decimal import Decimal

from .chinese import format_chinese_number
from .codes import GENERAL_TOKEN
from .dates import _format_date_value
from .numbers import format_number_value
from .program import FormatProgram
from .sections import _clean_display_pattern


def format_display_value(raw: str, program: FormatProgram, *, date_1904: bool) -> str | None:
    """Render all supported number-format families; None reports unavailable.

    Date syntax, locale handling, epoch conversion and elapsed-time rendering
    use the same implementation as XLSX. Numeric value storage stays separate.
    """
    try:
        if not program.supported:
            return None
        value = float(raw)
        if not math.isfinite(value):
            return None
        section, _selected = program.select(value)
        if section is None:
            return None
        language = program.section_directives(section).language_info
        if language is not None and language >> 16:
            return None
        is_date, _is_percentage = program.classify(section)
        if is_date:
            if re.search(r"(?i)b[12]", program.syntax(section)):
                return None
            return _format_date_value(value, section, date_1904, program.locale, context=program.date(section))
        if program.section_directives(section).dbnum:
            return format_chinese_number(Decimal(raw), section, program)
        general = GENERAL_TOKEN.search(program.syntax(section))
        if general:
            prefix = _clean_display_pattern(section[: general.start()])
            keep_sign = len(program.sections) == 1 and not program.conditional and "-" not in prefix and "(" not in prefix
            selected_value = raw if keep_sign else raw.removeprefix("-")
            return prefix + selected_value + _clean_display_pattern(section[general.end() :])
        return format_number_value(raw, section, program)
    except (ArithmeticError, TypeError, ValueError):
        return None
