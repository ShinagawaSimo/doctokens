"""Localized words and DBNum representations of individual date fields."""

from __future__ import annotations

from datetime import datetime

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


def date_number(value: int, token: str, dbnum: str | None) -> str:
    if dbnum is None:
        return str(value).zfill(len(token))
    digits = "○一二三四五六七八九"
    if token[0].lower() == "y":
        return "".join(digits[int(digit)] for digit in str(value).zfill(len(token)))
    tens, ones = divmod(value, 10)
    return (digits[tens] if tens > 1 else "") + ("十" if tens else "") + (digits[ones] if ones or not tens else "")


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
