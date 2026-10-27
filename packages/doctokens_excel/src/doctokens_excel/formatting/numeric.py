"""Fixed-point number, percentage and currency display from saved format codes."""

from __future__ import annotations

import math
import re

from .numbers import _format_number_value
from .program import FormatProgram
from .sections import _clean_display_pattern


def format_numeric_value(raw: str, program: FormatProgram) -> str | None:
    """Render supported decimal formats; None leaves other families to callers.

    Currency literals come from the format code. Locale never substitutes a
    different Unicode symbol (for example, U+00A5 and U+FFE5 remain distinct).
    """
    try:
        value = float(raw)
        if not math.isfinite(value):
            return None
        section, _selected = program.select(value)
        if section is None:
            return None
        if section.lower() == "general":
            return raw
        is_date, is_percentage = program.classify(section)
        directives = program.section_directives(section)
        if is_date or directives.dbnum:
            return None
        syntax = program.syntax(section)
        first = re.search(r"[0#?]", syntax)
        if first is None:
            return _clean_display_pattern(section) if not syntax.strip() else None
        last = max(index for index, char in enumerate(syntax) if char in "0#?")
        while last + 1 < len(syntax) and syntax[last + 1] == ",":
            last += 1
        # Dates, text, fractions and scientific notation have separate engines;
        # accepting only this core keeps their future dispatch unambiguous.
        if not re.fullmatch(r"[0#?,]+(?:\.[0#?]+)?,*", syntax[first.start() : last + 1]):
            return None
        return _format_number_value(value, raw, program.code, is_percentage, program.locale, program=program)
    except (ArithmeticError, ValueError):
        return None
