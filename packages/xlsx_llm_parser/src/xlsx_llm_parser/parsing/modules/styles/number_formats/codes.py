"""Codes."""

from __future__ import annotations

import re

# Built-in format codes from ECMA-376 §18.8.30.  Excel may omit the
# corresponding ``numFmt`` element for these IDs, so the parser needs the
# table even when styles.xml contains no custom formats.
_BUILTIN_FORMAT_CODES: dict[int, str] = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    5: "$#,##0_);($#,##0)",
    6: "$#,##0_);[Red]($#,##0)",
    7: "$#,##0.00_);($#,##0.00)",
    8: "$#,##0.00_);[Red]($#,##0.00)",
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "mm-dd-yy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yy h:mm",
    37: "#,##0 ;(#,##0)",
    38: "#,##0 ;[Red](#,##0)",
    39: "#,##0.00;(#,##0.00)",
    40: "#,##0.00;[Red](#,##0.00)",
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mm:ss.0",
    48: "##0.0E+0",
    49: "@",
    59: "t0",
    60: "t0.00",
    61: "t#,##0",
    62: "t#,##0.00",
    67: "t0%",
    68: "t0.00%",
    69: "t# ?/?",
    70: "t# ??/??",
    71: "ว/ด/ปปปป",
    72: "ว-ดดด-ปป",
    73: "ว-ดดด",
    74: "ดดด-ปป",
    75: "ช:นน",
    76: "ช:นน:ทท",
    77: "ว/ด/ปปปป ช:นน",
    78: "นน:ทท",
    79: "[ช]:นน:ทท",
    80: "นน:ทท.0",
    81: "d/m/bb",
}


# The standard table intentionally leaves several IDs language-dependent.
# These are the codes saved by the user's Simplified Chinese Excel for the
# common built-ins.  Other locales remain parameterized rather than guessed.
_LOCALE_FORMAT_CODES: dict[str, dict[int, str]] = {
    "zh-CN": {
        14: "yyyy/m/d",
        15: "d-mmm-yy",
        16: "d-mmm",
        17: "mmm-yy",
        18: "h:mm AM/PM",
        19: "h:mm:ss AM/PM",
        20: "h:mm",
        21: "h:mm:ss",
        22: "yyyy/m/d h:mm",
        27: 'yyyy"年"m"月"',
        28: 'm"月"d"日"',
        29: 'm"月"d"日"',
        30: "m-d-yy",
        31: 'yyyy"年"m"月"d"日"',
        32: 'h"时"mm"分"',
        33: 'h"时"mm"分"ss"秒"',
        34: '上午/下午 h"时"mm"分"',
        35: '上午/下午 h"时"mm"分"ss"秒"',
        36: 'yyyy"年"m"月"',
        50: 'yyyy"年"m"月"',
        51: 'm"月"d"日"',
        52: 'yyyy"年"m"月"',
        53: 'm"月"d"日"',
        54: 'm"月"d"日"',
        55: '上午/下午 h"时"mm"分"',
        56: '上午/下午 h"时"mm"分"ss"秒"',
        57: 'yyyy"年"m"月"',
        58: 'm"月"d"日"',
    },
}


_BUILTIN_DATE_IDS = {
    num_fmt_id
    for num_fmt_id, code in _BUILTIN_FORMAT_CODES.items()
    if num_fmt_id in set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59)) | set(range(71, 82))
}


# Built-in percentage format IDs.
_BUILTIN_PCT_IDS = {9, 10}


# Tokens that indicate a custom format string encodes a date or time.
_DATE_TOKENS_RE = re.compile(
    r"[yYmMdDhHsS]|AM/PM|am/pm|A/P|a/p|\[h\]|\[m\]|\[s\]",
)


# Percentage marker.
_PCT_RE = re.compile(r"%")


# Elapsed-time bracket sections that legitimately indicate a date/time format.
_ELAPSED_TIME_SECTIONS = {"[h]", "[hh]", "[m]", "[mm]", "[s]", "[ss]"}


def _date_scan_text(fmt_code: str) -> str:
    """Blank quoted literals and non-elapsed bracket sections from a format code.

    Date detection must ignore literal text like ``0 "pcs"`` or ``[DBNum1]``;
    only real date/time tokens (and the elapsed-time brackets ``[h]``/``[m]``/
    ``[s]``) should influence the date verdict.
    """
    out: list[str] = []
    i = 0
    n = len(fmt_code)
    while i < n:
        ch = fmt_code[i]
        if ch == '"':
            end = fmt_code.find('"', i + 1)
            if end == -1:
                end = n - 1
            out.append(" " * (end - i + 1))
            i = end + 1
        elif ch == "[":
            end = fmt_code.find("]", i)
            if end == -1:
                end = n - 1
            section = fmt_code[i : end + 1]
            out.append(section if section.lower() in _ELAPSED_TIME_SECTIONS else " " * len(section))
            i = end + 1
        elif ch in "\\_*":
            length = min(2, n - i)
            out.append(" " * length)
            i += length
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# ── Public API ──


def builtin_format_code(num_fmt_id: int, locale: str) -> str:
    return _localized_builtin_code(num_fmt_id, locale)


def resolve_format(num_fmt_id: int, fmt_code: str, locale: str) -> tuple[bool, bool]:
    # A custom ``numFmt`` is authoritative even when its ID happens to reuse
    # one of the built-in IDs.  The ID is only a fallback when the workbook
    # omitted a formatCode (the normal built-in representation).
    key_code = fmt_code or _localized_builtin_code(num_fmt_id, locale)
    is_date = bool(_DATE_TOKENS_RE.search(_date_scan_text(key_code)))
    if not fmt_code:
        is_date = is_date or num_fmt_id in _BUILTIN_DATE_IDS
    is_pct = bool(_PCT_RE.search(_date_scan_text(key_code)))
    if not fmt_code:
        is_pct = is_pct or num_fmt_id in _BUILTIN_PCT_IDS
    return is_date, is_pct


def _localized_builtin_code(num_fmt_id: int, locale: str) -> str:
    """Return the saved/display code for a built-in format.

    OOXML stores only the ID for built-ins.  The locale table is deliberately
    small and explicit: the only localized table currently defined by this
    parser is the user's Simplified Chinese Excel environment.  Unknown
    locales fall back to the standard OOXML table instead of silently using
    Chinese output.
    """
    locale = {"zh-cn": "zh-CN", "en-us": "en-US"}.get(locale.replace("_", "-").lower(), locale)
    localized = _LOCALE_FORMAT_CODES.get(locale, {}).get(num_fmt_id)
    return localized or _BUILTIN_FORMAT_CODES.get(num_fmt_id, "")
