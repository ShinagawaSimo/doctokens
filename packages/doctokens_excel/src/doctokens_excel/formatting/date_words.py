"""Localized words and DBNum representations of individual date fields."""

from __future__ import annotations

from datetime import datetime

from .chinese_digits import DBNUM_DIGITS, DBNUM_UNITS, integer_text

_MONTHS = (
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
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def date_number(value: int, token: str, dbnum: str | None, *, padding: bool = True, elapsed: bool = False) -> str:
    if dbnum is None:
        return str(value).zfill(len(token))
    digits = DBNUM_DIGITS[dbnum]
    if token[0].lower() == "y" or (dbnum == "dbnum3" and not elapsed):
        return "".join(digits[int(digit)] for digit in str(value).zfill(len(token)))
    if elapsed:
        return integer_text(value, digits, DBNUM_UNITS[dbnum])
    tens, ones = divmod(value, 10)
    unit = "拾" if dbnum == "dbnum2" else "十"
    return (
        (digits[0] * max(0, len(token) - len(str(value))) if padding else "")
        + (digits[tens] if tens > 1 or (tens and dbnum == "dbnum2") else "")
        + (unit if tens else "")
        + (digits[ones] if ones or not tens else "")
    )


def month_name(month: int, *, short: bool, locale: str) -> str:
    if locale == "zh-cn":
        return f"{month}月"
    name = _MONTHS[month - 1]
    return name[:3] if short else name


def weekday_name(year: int, month: int, day: int, *, short: bool, locale: str) -> str:
    # Preserve the existing empty weekday for the fictitious 1900 leap day.
    try:
        value = datetime(year, month, day).weekday()
    except ValueError:
        return ""
    if locale == "zh-cn":
        return ("周" if short else "星期") + "一二三四五六日"[value]
    return _DAYS[value][:3] if short else _DAYS[value]
