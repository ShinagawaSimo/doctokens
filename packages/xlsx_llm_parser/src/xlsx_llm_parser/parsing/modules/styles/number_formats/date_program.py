"""Compile date syntax once; execute only value-dependent operations per cell."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .codes import _DATE_FIELD_RE, _date_scan_text
from .date_context import DateContext
from .date_words import date_number, month_name, weekday_name


@dataclass(frozen=True, slots=True)
class DateProgram:
    context: DateContext
    operations: tuple[tuple[str, str], ...]
    fraction_places: int | None
    has_ampm: bool

    def render(self, date: tuple[int, int, int], seconds: int, milliseconds: int, elapsed_days: int) -> str:
        year, month, day = date
        hour, remainder = divmod(seconds, 3600)
        minute, second = divmod(remainder, 60)
        hour_value = hour % 12 or 12 if self.has_ampm else hour
        total = elapsed_days * 86400 + seconds
        locale, dbnum = self.context.locale, self.context.dbnum
        output: list[str] = []
        for kind, token in self.operations:
            if kind == "literal":
                value = token
            elif kind == "year":
                value = date_number(year % 100 if len(token) == 2 else year, token, dbnum)
            elif kind == "day":
                value = date_number(day, token, dbnum)
            elif kind == "weekday":
                value = weekday_name(year, month, day, short=len(token) == 3, locale=locale)
            elif kind == "month":
                value = date_number(month, token, dbnum)
            elif kind == "month-name":
                value = month_name(month, short=len(token) != 4, locale=locale)
                if len(token) > 4:
                    value = value[0]
            elif kind in {"hour", "minute", "second"}:
                number = hour_value if kind == "hour" else minute if kind == "minute" else second
                value = str(number) if len(token) == 1 else str(number).zfill(2)
            elif kind == "elapsed":
                number = total // (3600 if token[0] == "h" else 60 if token[0] == "m" else 1)
                value = str(number).zfill(2 if len(token) == 2 else 1)
            elif kind == "fraction":
                value = f"{milliseconds:03d}"[: len(token)]
                if token.endswith("#"):
                    value = value.rstrip("0")
                elif token.endswith("?"):
                    value = value.rstrip("0") + " " * (len(token) - len(value.rstrip("0")))
                value = "." + value
            elif token == "上午/下午" or locale.lower().startswith("zh"):
                value = ("上" if hour < 12 else "下") if token.upper() == "A/P" else ("上午" if hour < 12 else "下午")
            else:
                value = ("A" if hour < 12 else "P") if token.upper() == "A/P" else ("AM" if hour < 12 else "PM")
            output.append(value)
        return "".join(output)


def compile_date(context: DateContext) -> DateProgram:
    section, locale, _dbnum = context
    syntax = _date_scan_text(section)
    fraction = re.search(r"(?i)(?:s+|\[s+\])\.([0#?]+)", syntax)
    places = len(fraction.group(1)) if fraction else None
    if places is not None and places > 3:
        raise ValueError("Sub-millisecond date display is not supported")
    operations: list[tuple[str, str]] = []
    previous = ""
    i = 0
    while i < len(section):
        ch = section[i]
        if ch == '"':
            end = section.find('"', i + 1)
            end = len(section) if end < 0 else end
            operations.append(("literal", section[i + 1 : end]))
            i = min(len(section), end + 1)
            continue
        if ch == "\\":
            if i + 1 < len(section):
                operations.append(("literal", section[i + 1]))
            i += 2
            continue
        marker = re.match(r"(?i)(AM/PM|A/P|上午/下午)", section[i:])
        if marker:
            operations.append(("ampm", marker.group()))
            i += len(marker.group())
            previous = "ampm"
            continue
        if ch == "[":
            end = section.find("]", i + 1)
            token = section[i + 1 : end].lower() if end >= 0 else ""
            if token in {"h", "hh", "m", "mm", "s", "ss"}:
                operations.append(("elapsed", token))
                previous = token[0]
            i = end + 1 if end >= 0 else i + 1
            continue
        match = _DATE_FIELD_RE.match(section, i)
        if match:
            token = match.group()
            lower = token[0].lower()
            if lower == "a" and locale != "zh-cn":
                raise ValueError("Localized weekday token requires zh-CN")
            if lower in {"a", "d"}:
                kind = "day" if lower == "d" and len(token) <= 2 else "weekday"
                previous = "d"
            elif lower == "y":
                kind, previous = "year", "y"
            elif lower == "h":
                kind, previous = "hour", "h"
            elif lower == "s":
                kind, previous = "second", "s"
            else:
                minute = previous == "h" or bool(re.match(r"\s*[:.]?\s*[sS]", syntax[i + len(token) :]))
                kind = "minute" if minute else "month" if len(token) <= 2 else "month-name"
                previous = "n" if minute else "M"
            operations.append((kind, token))
            i += len(token)
            if lower == "s" and (suffix := re.match(r"\.[0#?]+", section[i:])):
                operations.append(("fraction", suffix.group()[1:]))
                i += len(suffix.group())
            continue
        if ch in "_*":
            if ch == "_":
                operations.append(("literal", " "))
            i += 2 if i + 1 < len(section) else 1
            continue
        operations.append(("literal", ch))
        i += 1
    return DateProgram(context, tuple(operations), places, bool(re.search(r"(?i)AM/PM|A/P", syntax)) or "上午/下午" in syntax)
