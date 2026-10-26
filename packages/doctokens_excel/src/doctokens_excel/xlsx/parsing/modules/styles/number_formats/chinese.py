"""Simplified Chinese Excel DBNum counting formats.

DBNum is locale-dependent and uses positional units, not just replacement
digits. Keep this implementation independent of Word's numbering rules.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .codes import _date_scan_text
from .sections import _clean_display_pattern, _section_directives, _split_format_sections


def format_chinese_integer(value: Decimal, section: str, fmt_code: str, locale: str) -> str | None:
    """Render DBNum1/2 General integers; leave unverified variants untouched."""
    mode = _section_directives(section)[2]
    if mode not in {"dbnum1", "dbnum2"} or not _simplified_chinese(section, locale):
        return None
    syntax = _date_scan_text(section)
    token = re.search(r"(?i)General", syntax)
    if token is None or syntax[: token.start()].strip() or syntax[token.end() :].strip():
        return None
    magnitude = abs(value)
    # General's decimal/scientific and width-dependent forms need separate
    # Office evidence. Do not manufacture a Chinese display for those cases.
    if magnitude != magnitude.to_integral_value() or magnitude >= Decimal("1e15"):
        return None
    digits, units = ("〇一二三四五六七八九", "十百千") if mode == "dbnum1" else ("零壹贰叁肆伍陆柒捌玖", "拾佰仟")
    rendered = _integer_text(int(magnitude), digits, units)
    prefix = _clean_display_pattern(section[: token.start()])
    if value < 0 and len(_split_format_sections(fmt_code)) == 1 and "-" not in prefix and "(" not in prefix:
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


def _integer_text(value: int, digits: str, units: str) -> str:
    if value == 0:
        return digits[0]
    groups: list[int] = []
    while value:
        value, group = divmod(value, 10_000)
        groups.append(group)
    output: list[str] = []
    skipped = False
    for position in range(len(groups) - 1, -1, -1):
        group = groups[position]
        if not group:
            skipped = True
            continue
        if output and (skipped or group < 1000):
            output.append(digits[0])
        output.append(_group_text(group, digits, units))
        output.append(("", "万", "亿", "万亿")[position])
        skipped = False
    return "".join(output)


def _group_text(value: int, digits: str, units: str) -> str:
    output: list[str] = []
    skipped = False
    for position in range(3, -1, -1):
        digit, value = divmod(value, 10**position)
        if not digit:
            skipped = bool(output)
            continue
        if skipped:
            output.append(digits[0])
        output.append(digits[digit])
        if position:
            output.append(units[position - 1])
        skipped = False
    return "".join(output)
