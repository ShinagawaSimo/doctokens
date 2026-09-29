"""Dates."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from .codes import _date_scan_text


class _SerialDateTime(NamedTuple):
    """Calendar components derived from one SpreadsheetML serial value.

    ``day`` is the serial day before the calendar conversion.  Keeping it in
    the result lets elapsed-time formats use the same split as date formats.
    """

    date: tuple[int, int, int]
    seconds: int
    milliseconds: int
    day: int


# Excel's 1900 workbook mode retains Lotus 1-2-3's fictitious leap day.  The
# named constant makes this an explicit compatibility rule rather than a
# fixture-specific ``if whole == 60`` branch.
_EXCEL_1900_LEAP_SERIAL = 60


def _format_date_value(serial: float, fmt_code: str, date_1904: bool, locale: str) -> str:
    fraction = re.search(r"(?i)(?:s+|\[s+\])\.([0#?]+)", _date_scan_text(fmt_code))
    if fraction:
        places = len(fraction.group(1))
        if places > 3:
            raise ValueError("Sub-millisecond date display is not supported")
        quantum = Decimal(1).scaleb(-places)
        serial = float((Decimal(str(serial)) * 86400).quantize(quantum, rounding=ROUND_HALF_UP) / 86400)
    serial_time = _serial_datetime(serial, date_1904)
    return _format_datetime_code(
        fmt_code,
        serial_time.date,
        serial_time.seconds,
        serial_time.milliseconds,
        serial_time.day,
        locale,
    )


def _serial_datetime(serial: float, date_1904: bool) -> _SerialDateTime:
    """Split a signed serial into a calendar date and time-of-day.

    ISO/OOXML defines serial day ``0`` for the 1900 system relative to
    1899-12-30.  Excel's normal 1900 display has the historical one-day
    adjustment for serials 1--59 and exposes serial 60 as 1900-02-29.  The
    adjustment is isolated in ``_serial_day_date`` so the arithmetic here
    remains the same for every date and time format.
    """
    whole = math.floor(serial)
    fraction = serial - whole
    total_milliseconds = round(fraction * 86400 * 1000)
    if total_milliseconds >= 86400 * 1000:
        whole += 1
        total_milliseconds -= 86400 * 1000
    seconds, milliseconds = divmod(total_milliseconds, 1000)
    date = _serial_day_date(whole, date_1904)
    return _SerialDateTime(date, seconds, milliseconds, whole)


def _serial_day_date(serial_day: int, date_1904: bool) -> tuple[int, int, int]:
    """Return calendar components for one integer serial day."""
    if date_1904:
        epoch = datetime(1904, 1, 1)
        value = epoch + timedelta(days=serial_day)
        return value.year, value.month, value.day

    if serial_day < 0:
        # Negative values follow the ISO/OOXML 1899-12-30 base directly.
        epoch = datetime(1899, 12, 30)
        value = epoch + timedelta(days=serial_day)
        return value.year, value.month, value.day
    if serial_day == _EXCEL_1900_LEAP_SERIAL:
        # Python's Gregorian calendar cannot represent this Office-visible
        # compatibility date, so expose its documented components directly.
        return 1900, 2, 29

    # Excel serials 0..59 use 1899-12-31; values after the fictitious day are
    # shifted back once, equivalent to the OOXML 1899-12-30 base.
    ordinal = serial_day if serial_day < _EXCEL_1900_LEAP_SERIAL else serial_day - 1
    value = datetime(1899, 12, 31) + timedelta(days=ordinal)
    return value.year, value.month, value.day


def _format_datetime_code(
    section: str,
    date: tuple[int, int, int],
    seconds: int,
    milliseconds: int,
    elapsed_days: int,
    locale: str,
) -> str:
    year, month, day = date
    hour, remainder = divmod(seconds, 3600)
    minute, second = divmod(remainder, 60)
    syntax = _date_scan_text(section)
    has_ampm = bool(re.search(r"(?i)AM/PM|A/P", syntax)) or "上午/下午" in syntax
    hour_value = hour % 12 or 12 if has_ampm else hour
    total_seconds = elapsed_days * 86400 + seconds
    output: list[str] = []
    i = 0
    previous_field = ""
    while i < len(section):
        if section[i] == '"':
            end = section.find('"', i + 1)
            if end < 0:
                end = len(section)
            output.append(section[i + 1 : end])
            i = min(len(section), end + 1)
            continue
        if section[i] == "\\":
            if i + 1 < len(section):
                output.append(section[i + 1])
                i += 2
            else:
                i += 1
            continue
        if section.startswith("上午/下午", i):
            output.append("上午" if hour < 12 else "下午")
            i += len("上午/下午")
            previous_field = "ampm"
            continue
        marker = re.match(r"(?i)(AM/PM|A/P)", section[i:])
        if marker:
            value = marker.group(1)
            if value.upper() == "A/P":
                output.append(("上" if hour < 12 else "下") if locale.lower().startswith("zh") else ("A" if hour < 12 else "P"))
            else:
                output.append(
                    "上午"
                    if hour < 12 and locale.lower().startswith("zh")
                    else "AM"
                    if hour < 12
                    else "下午"
                    if locale.lower().startswith("zh")
                    else "PM"
                )
            i += len(value)
            previous_field = "ampm"
            continue
        if section[i] == "[":
            end = section.find("]", i + 1)
            if end >= 0:
                token = section[i + 1 : end].lower()
                if token in {"h", "hh", "m", "mm", "s", "ss"}:
                    value = {
                        "h": total_seconds // 3600,
                        "hh": total_seconds // 3600,
                        "m": total_seconds // 60,
                        "mm": total_seconds // 60,
                        "s": total_seconds,
                        "ss": total_seconds,
                    }[token]
                    output.append(str(value).zfill(2 if token in {"hh", "mm", "ss"} else 1))
                    i = end + 1
                    previous_field = token[0]
                    continue
        token_match = re.match(r"(?i)(y+|m+|d+|h+|s+)", section[i:])
        if token_match:
            token = token_match.group(0)
            lower = token[0].lower()
            if lower == "y":
                output.append(str(year % 100).zfill(2) if len(token) == 2 else str(year).zfill(len(token)))
                previous_field = "y"
            elif lower == "d":
                if len(token) == 1:
                    output.append(str(day))
                elif len(token) == 2:
                    output.append(str(day).zfill(2))
                elif len(token) == 3:
                    output.append(
                        ("周" if locale.lower().startswith("zh") else "")
                        + _weekday_name(year, month, day, short=True, locale=locale)
                    )
                else:
                    output.append(
                        ("星期" if locale.lower().startswith("zh") else "")
                        + _weekday_name(year, month, day, short=False, locale=locale)
                    )
                previous_field = "d"
            elif lower == "h":
                output.append(str(hour_value) if len(token) == 1 else str(hour_value).zfill(2))
                previous_field = "h"
            elif lower == "s":
                output.append(str(second) if len(token) == 1 else str(second).zfill(2))
                i += len(token)
                # A fractional-second suffix belongs to the seconds token;
                # treating its zeroes as literals would always print ``.0``.
                fraction_match = re.match(r"\.(?:[0#?]+)", section[i:])
                if fraction_match:
                    fraction_code = fraction_match.group(0)[1:]
                    fraction_text = f"{milliseconds:03d}"[: len(fraction_code)]
                    if fraction_code.endswith("#"):
                        fraction_text = fraction_text.rstrip("0")
                    elif fraction_code.endswith("?"):
                        fraction_text = fraction_text.rstrip("0") + " " * (len(fraction_code) - len(fraction_text.rstrip("0")))
                    output.append("." + fraction_text)
                    i += len(fraction_match.group(0))
                previous_field = "s"
                continue
            else:  # m: month unless adjacent to hour/second, where it is minute.
                after = syntax[i + len(token) :]
                minute_token = previous_field == "h" or bool(re.match(r"\s*[:.]?\s*[sS]", after))
                if minute_token:
                    output.append(str(minute) if len(token) == 1 else str(minute).zfill(2))
                    previous_field = "n"
                elif len(token) == 1:
                    output.append(str(month))
                    previous_field = "M"
                elif len(token) == 2:
                    output.append(str(month).zfill(2))
                    previous_field = "M"
                elif len(token) == 3:
                    output.append(_month_name(month, short=True, locale=locale))
                    previous_field = "M"
                elif len(token) == 4:
                    output.append(_month_name(month, short=False, locale=locale))
                    previous_field = "M"
                else:
                    output.append(_month_name(month, short=True, locale=locale)[0])
                    previous_field = "M"
            i += len(token)
            continue
        if section[i] == "_":
            output.append(" ")
            i += 2 if i + 1 < len(section) else 1
            continue
        if section[i] == "*":
            i += 2 if i + 1 < len(section) else 1
            continue
        if section[i] == "[":
            end = section.find("]", i + 1)
            i = end + 1 if end >= 0 else i + 1
            continue
        output.append(section[i])
        i += 1
    return "".join(output)


def _month_name(month: int, *, short: bool, locale: str) -> str:
    names = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    short_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return (short_names if short else names)[month - 1]


def _weekday_name(year: int, month: int, day: int, *, short: bool, locale: str) -> str:
    try:
        value = datetime(year, month, day).weekday()
    except ValueError:
        return ""
    if locale.lower().startswith("zh"):
        return ("一", "二", "三", "四", "五", "六", "日")[value]
    return (
        ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[value]
        if short
        else ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[value]
    )
