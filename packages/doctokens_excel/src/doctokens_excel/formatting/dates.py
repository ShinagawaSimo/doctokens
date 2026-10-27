"""Dates."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from .date_context import DateContext, date_context
from .date_program import DateProgram, compile_date


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


def time_formula_bar_value(value: Decimal, section: str, locale: str) -> str | None:
    """Reconstruct the zh-CN formula bar for a time within the first day.

    The formula bar omits fractional seconds independently of the cell's
    fractional-second display format. It is not a lossless serial encoding.
    Date, elapsed, AM/PM and other locale-dependent edit forms remain unknown.
    """
    if locale.replace("_", "-").lower() != "zh-cn" or not 0 <= value < 1:
        return None
    if not re.fullmatch(r"h{1,2}:mm:ss(?:\.0{1,3})?", section, re.IGNORECASE):
        return None
    # Resolve binary serial noise at Excel's millisecond precision before
    # taking whole seconds, without rounding to the cell's display precision.
    milliseconds = int((value * 86_400_000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if milliseconds >= 86_400_000:
        return None
    hour, remainder = divmod(milliseconds // 1000, 3600)
    minute, second = divmod(remainder, 60)
    return f"{hour}:{minute:02d}:{second:02d}"


def _format_date_value(
    serial: float, fmt_code: str, date_1904: bool, locale: str, *, context: DateContext | DateProgram | None = None
) -> str:
    program = context if isinstance(context, DateProgram) else compile_date(context or date_context(fmt_code, locale))
    if program.fraction_places is not None:
        quantum = Decimal(1).scaleb(-program.fraction_places)
        serial = float((Decimal(str(serial)) * 86400).quantize(quantum, rounding=ROUND_HALF_UP) / 86400)
    value = _serial_datetime(serial, date_1904)
    return program.render(value.date, value.seconds, value.milliseconds, value.day)


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
