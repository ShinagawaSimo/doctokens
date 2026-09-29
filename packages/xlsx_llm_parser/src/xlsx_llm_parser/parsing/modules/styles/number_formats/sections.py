"""Sections."""

from __future__ import annotations

import re


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


def _section_directives(section: str) -> tuple[list[tuple[str, float]], str | None, str | None]:
    """Read conditions, locale currency, and DBNum directives from a section."""
    conditions: list[tuple[str, float]] = []
    currency: str | None = None
    dbnum: str | None = None
    # Ignore bracket-looking text inside quoted or escaped literals.
    directives = re.sub(r'"[^\"]*"|\\.|_.|\*.', lambda match: " " * len(match.group()), section)
    for match in re.finditer(r"\[([^\]]*)\]", directives):
        value = match.group(1)
        lower = value.lower()
        condition = _CONDITION_RE.fullmatch(value)
        if condition:
            conditions.append((condition.group(1), float(condition.group(2))))
        elif lower.startswith("$"):
            body = value[1:]
            currency = body.split("-", 1)[0] or None
        elif lower.startswith("dbnum"):
            dbnum = lower
    return conditions, currency, dbnum


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


def _select_format_section(value: float, fmt_code: str) -> tuple[str | None, float]:
    sections = _split_format_sections(fmt_code)[:3]
    if any(_section_directives(section)[0] for section in sections):
        for section in sections:
            conditions, _currency, _dbnum = _section_directives(section)
            if not conditions or all(_condition_matches(value, condition) for condition in conditions):
                return section, value
        # Excel fills the cell with hashes if no condition applies. Width
        # rendering is outside this parser; never pick a failed condition.
        return None, value
    if len(sections) == 1:
        return sections[0], value
    if len(sections) == 2:
        if value < 0:
            return sections[1], abs(value)
        return sections[0], value
    if value > 0:
        return sections[0], value
    if value < 0:
        return sections[1], abs(value)
    return sections[2], value


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
                body = directive[1:].split("-", 1)[0]
                if body:
                    out.append(body)
            i = end + 1
        else:
            out.append(char)
            i += 1
    return "".join(out)
