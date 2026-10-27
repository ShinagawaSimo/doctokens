"""Simplified Chinese Excel DBNum counting formats.

DBNum is locale-dependent and uses positional units, not just replacement
digits. Keep this implementation independent of Word's numbering rules.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING

from .chinese_digits import DBNUM_DIGITS, DBNUM_UNITS, integer_text
from .codes import GENERAL_TOKEN, _date_scan_text
from .numbers import format_number_value
from .sections import _clean_display_pattern, _section_directives

if TYPE_CHECKING:
    from .program import FormatProgram


def format_chinese_number(value: Decimal, section: str, program: FormatProgram) -> str | None:
    """Render Simplified Chinese DBNum General and fixed-point numbers."""
    mode = _section_directives(section)[2]
    if mode not in {"dbnum1", "dbnum2", "dbnum3"} or not _simplified_chinese(section, program.locale):
        return None
    syntax = _date_scan_text(section)
    token = GENERAL_TOKEN.search(syntax)
    magnitude = abs(value)
    if magnitude >= Decimal("1e16"):
        return None
    digits, units = DBNUM_DIGITS[mode], DBNUM_UNITS[mode]
    if token is None:
        if _section_directives(section).currency or re.search(r"[%/@Ee]", syntax):
            return None
        return format_number_value(str(value), section, program, digits=digits)
    if syntax[: token.start()].strip() or syntax[token.end() :].strip():
        return None
    rendered = integer_text(int(magnitude), digits, units)
    if magnitude != magnitude.to_integral_value():
        fraction = format(magnitude, "f").partition(".")[2].rstrip("0")
        rendered += "." + fraction.translate(str.maketrans("0123456789", digits))
    prefix = _clean_display_pattern(section[: token.start()])
    if value < 0 and len(program.sections) == 1 and not program.conditional and "-" not in prefix and "(" not in prefix:
        rendered = "-" + rendered
    return prefix + rendered + _clean_display_pattern(section[token.end() :])


def _simplified_chinese(section: str, locale: str) -> bool:
    # An explicit LCID wins over the parser's default UI locale. Ignore
    # bracket-like strings inside literal text, as section selection does.
    directives = re.sub(r'"[^\"]*"|\\.|_.|\*.', lambda match: " " * len(match.group()), section)
    lcid = re.search(r"\[\$[^\]]*-([0-9a-f]+)\]", directives, re.IGNORECASE)
    if lcid:
        return int(lcid.group(1), 16) == 0x804
    return locale.replace("_", "-").lower() == "zh-cn"
