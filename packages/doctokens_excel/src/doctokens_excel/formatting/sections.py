"""Sections."""

from __future__ import annotations

import math
import re
from typing import NamedTuple


def _split_format_sections(fmt_code: str) -> list[str]:
    """Split sections at semicolons outside literals and bracket directives."""
    sections: list[str] = []
    start = 0
    quote = False
    escaped = False
    bracket = 0
    for index, char in enumerate(fmt_code):
        if escaped:
            escaped = False
            continue
        if char in "\\_*" and not quote:
            escaped = True
            continue
        if char == '"':
            quote = not quote
            continue
        if not quote and char == "[":
            bracket += 1
            continue
        if not quote and char == "]" and bracket:
            bracket -= 1
            continue
        if char == ";" and not quote and bracket == 0:
            sections.append(fmt_code[start:index])
            start = index + 1
    sections.append(fmt_code[start:])
    return sections


_CONDITION_RE = re.compile(r"^(<=|>=|<>|=|<|>)([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)$")


class SectionDirectives(NamedTuple):
    conditions: list[tuple[str, float]]
    currency: str | None
    dbnum: str | None
    language_info: int | None


def directive_values(section: str) -> list[str]:
    masked = re.sub(r'"[^\"]*"|\\.|_.|\*.', lambda match: " " * len(match.group()), section)
    return re.findall(r"\[([^\]]*)\]", masked)


def currency_parts(body: str) -> tuple[str | None, int | None]:
    symbol, separator, language = body.rpartition("-")
    if separator and re.fullmatch(r"[0-9a-fA-F]{1,8}", language):
        return symbol or None, int(language, 16)
    return body or None, None


def supported_directives(section: str) -> bool:
    for value in directive_values(section):
        lower = value.lower()
        if lower.startswith("$") or lower in {"h", "hh", "m", "mm", "s", "ss", "dbnum1", "dbnum2", "dbnum3"}:
            continue
        if lower in {"black", "blue", "cyan", "green", "magenta", "red", "white", "yellow"}:
            continue
        color = re.fullmatch(r"(?:color|颜色)(\d+)", lower)
        if color and 1 <= int(color.group(1)) <= 56:
            continue
        condition = _CONDITION_RE.fullmatch(value)
        if condition and math.isfinite(float(condition.group(2))):
            continue
        return False
    return True


def balanced_format(code: str) -> bool:
    quoted = False
    bracketed = False
    escaped = False
    for char in code:
        if escaped:
            escaped = False
        elif char == '"' and not bracketed:
            quoted = not quoted
        elif quoted:
            continue
        elif char in "\\_*" and not bracketed:
            escaped = True
        elif char == "[":
            if bracketed:
                return False
            bracketed = True
        elif char == "]":
            if not bracketed:
                return False
            bracketed = False
    return not quoted and not bracketed and not escaped


def _section_directives(section: str) -> SectionDirectives:
    """Read directives without losing the language/calendar/number-system bits."""
    conditions: list[tuple[str, float]] = []
    currency: str | None = None
    dbnum: str | None = None
    language_info: int | None = None
    # Ignore bracket-looking text inside quoted or escaped literals.
    for value in directive_values(section):
        lower = value.lower()
        condition = _CONDITION_RE.fullmatch(value)
        if condition:
            conditions.append((condition.group(1), float(condition.group(2))))
        elif lower.startswith("$"):
            currency, language_info = currency_parts(value[1:])
        elif lower.startswith("dbnum"):
            dbnum = lower
    return SectionDirectives(conditions, currency, dbnum, language_info)


def _condition_matches(value: float, condition: tuple[str, float]) -> bool:
    operator, target = condition
    return {
        "=": value == target,
        "<>": value != target,
        "<": value < target,
        ">": value > target,
        "<=": value <= target,
        ">=": value >= target,
    }[operator]


def _clean_display_pattern(pattern: str, *, keep_elapsed: bool = False) -> str:
    """Remove format directives while retaining visible literals."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == '"':
            end = i + 1
            while end < len(pattern) and pattern[end] != '"':
                end += 1
            out.append(pattern[i + 1 : end])
            i = min(len(pattern), end + 1)
        elif char == "\\":
            if i + 1 < len(pattern):
                out.append(pattern[i + 1])
                i += 2
            else:
                i += 1
        elif char == "_":
            out.append(" ")
            i += 2 if i + 1 < len(pattern) else 1
        elif char == "*":
            # Fill characters affect the visual cell width, not the value.
            i += 2 if i + 1 < len(pattern) else 1
        elif char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(char)
                i += 1
                continue
            directive = pattern[i + 1 : end]
            if keep_elapsed and directive.lower() in {"h", "hh", "m", "mm", "s", "ss"}:
                out.append(pattern[i : end + 1])
            elif directive.startswith("$"):
                body, _language = currency_parts(directive[1:])
                if body:
                    out.append(body)
            i = end + 1
        else:
            out.append(char)
            i += 1
    return "".join(out)
