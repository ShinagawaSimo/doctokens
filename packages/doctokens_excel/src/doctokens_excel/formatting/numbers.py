"""Numbers."""

from __future__ import annotations

import re
from decimal import Decimal

from .decimal import format_decimal_pattern
from .fractions import format_fraction
from .program import FormatProgram
from .scientific import format_scientific
from .sections import _clean_display_pattern


def format_number_value(raw: str, section: str, program: FormatProgram, *, digits: str | None = None) -> str | None:
    value = Decimal(raw)
    magnitude = abs(value)
    dbnum = program.section_directives(section).dbnum
    syntax = program.syntax(section)
    if "@" in syntax and not re.search(r"[0#?]", syntax):
        return raw
    if dbnum and digits is None:
        return None

    magnitude *= Decimal(100) ** syntax.count("%")
    core_match = re.search(r"[0#?]", syntax)
    if core_match is None:
        return _clean_display_pattern(section)
    first = core_match.start()
    fraction_match = re.search(r"(?:[0#?]+\s+)?[0#?]+\s*/\s*(?:[1-9]\d*|[0#?]+)", syntax)
    if fraction_match:
        first = fraction_match.start()
        last = fraction_match.end() - 1
    else:
        if first and syntax[first - 1] == ".":
            first -= 1
        last = max(index for index, char in enumerate(syntax) if char in "0#?")
        while last + 1 < len(syntax) and syntax[last + 1] in ",.":
            last += 1
    prefix = _clean_display_pattern(section[:first])
    core = section[first : last + 1]
    suffix = _clean_display_pattern(section[last + 1 :])

    # Office accepts the uppercase ``E+``/``E-`` spellings for scientific
    # notation.  A lowercase ``e`` is ordinary literal text in a custom code
    # and must not silently trigger a scientific re-render.
    if re.fullmatch(r"[0#?]+(?:\.[0#?]+)?E[+-][0#?]+", core):
        rendered = format_scientific(magnitude, core)
    elif re.search(r"e[+-][0#?]+", core):
        # MS-OI29500 records both spellings in the grammar, but Office's
        # display engine accepts only uppercase E markers.  Preserve the
        # lexical value for the unsupported lowercase form.
        return None
    elif re.fullmatch(r"(?:[0#?]+\s+)?[0#?]+\s*/\s*(?:[1-9]\d*|[0#?]+)", syntax[first : last + 1]):
        rendered = format_fraction(magnitude, syntax[first : last + 1])
    elif re.fullmatch(r"[0#?,.\s]+", syntax[first : last + 1]):
        rendered = format_decimal_pattern(magnitude, program.decimal(core), digits=digits)
    else:
        return None
    if value < 0 and len(program.sections) == 1 and not program.conditional and not _explicit_negative_prefix(section):
        rendered = "-" + rendered
    return prefix + rendered + suffix


def _explicit_negative_prefix(section: str) -> bool:
    """Whether a selected numeric section already writes its own sign."""
    cleaned = _clean_display_pattern(section)
    match = re.search(r"[0#?]", cleaned)
    prefix = cleaned if match is None else cleaned[: match.start()]
    return "-" in prefix or "(" in prefix
