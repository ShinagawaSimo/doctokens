"""Temporary cases awaiting the number-format files in docs/真实测试文件清单.md.

Basic fraction, Chinese General and h:mm:ss.0 behavior belongs to file goldens.
These cases cover pending custom formats/boundaries and locale API guards;
unsupported valid formats are migration gaps, not malformed-file exceptions.
"""

import pytest
from xlsx_llm_parser.parsing.modules.styles.number_format import format_value, formula_bar_value


@pytest.mark.parametrize(
    ("raw", "code", "expected"),
    [
        ("1.25", "# ??/??", "1 1/4"),
        ("-1.25", "# ??/??", "-1 1/4"),
        ("1", "# ??/??", "1"),
        ("0.25", "00/00", "01/04"),
        ("0.25", "?0/?0", "1/4"),
        ("0.25", "# ??/16", "4/16"),
        ("0.25", '"  "# ??/??"  "', "  1/4  "),
    ],
)
def test_fraction_text_omits_only_alignment_padding(raw: str, code: str, expected: str) -> None:
    assert format_value(164, code, raw, date_1904=False, locale="zh-CN") == expected
    assert formula_bar_value(raw, code, "zh-CN") == raw


@pytest.mark.parametrize(
    ("raw", "lower", "upper"),
    [
        ("0", "〇", "零"),
        ("10", "一十", "壹拾"),
        ("101", "一百〇一", "壹佰零壹"),
        ("1010", "一千〇一十", "壹仟零壹拾"),
        ("10000", "一万", "壹万"),
        ("10001", "一万〇一", "壹万零壹"),
        ("10010", "一万〇一十", "壹万零壹拾"),
        ("100000001", "一亿〇一", "壹亿零壹"),
        ("100010000", "一亿〇一万", "壹亿零壹万"),
        ("123456789", "一亿二千三百四十五万六千七百八十九", "壹亿贰仟叁佰肆拾伍万陆仟柒佰捌拾玖"),
        ("-1234", "-一千二百三十四", "-壹仟贰佰叁拾肆"),
    ],
)
def test_chinese_general_uses_units_and_internal_zeroes(raw: str, lower: str, upper: str) -> None:
    for mode, expected in ((1, lower), (2, upper)):
        code = f"[DBNum{mode}][$-804]General"
        assert format_value(176, code, raw, date_1904=False, locale="zh-CN") == expected
        assert formula_bar_value(raw, code, "zh-CN") == raw


@pytest.mark.parametrize(
    ("code", "locale", "expected"),
    [
        ("[DBNum1]General", "zh_CN", "一千二百三十四"),
        ("[DBNum1]General", "en-US", "1234"),
        ("[DBNum1][$-804]General", "en-US", "一千二百三十四"),
        ("[DBNum1][$-0804]General", "en-US", "一千二百三十四"),
        ("[DBNum1][$-404]General", "zh-CN", "1234"),
        ("[DBNum1][$-411]General", "zh-CN", "1234"),
        ('[DBNum1][$-804]"ID1: "General" 件"', "zh-CN", "ID1: 一千二百三十四 件"),
        ('[DBNum1]"[$-411]"General', "zh-CN", "[$-411]一千二百三十四"),
        ('[>0][DBNum1]General;[DBNum2]General;"zero"', "zh-CN", "一千二百三十四"),
    ],
)
def test_chinese_locale_and_literals(code: str, locale: str, expected: str) -> None:
    assert format_value(176, code, "1234", date_1904=False, locale=locale) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("1234.56", "[DBNum1][$-804]General"),
        ("1000000000000000", "[DBNum2][$-804]General"),
        ("1234", "[DBNum3][$-804]General"),
        ("1234", "[DBNum1]0"),
        ("44927", "[DBNum1]yyyy-mm-dd"),
    ],
)
def test_unverified_chinese_forms_keep_the_saved_value(raw: str, code: str) -> None:
    assert format_value(176, code, raw, date_1904=False, locale="zh-CN") == raw
    assert formula_bar_value(raw, code, "zh-CN") is None


def test_millisecond_time_display_and_formula_bar_are_independent() -> None:
    code, expected = "hh:mm:ss.000", "12:30:00.125"
    raw = "0.52083478009259254"
    assert format_value(176, code, raw, date_1904=False, locale="zh-CN") == expected
    assert formula_bar_value(raw, code, "zh-CN") == "12:30:00"


@pytest.mark.parametrize(
    ("raw", "code", "expected"),
    [
        ("0", "hh:mm:ss.000", "0:00:00"),
        ("0.5208333333333333", "h:mm:ss.0", "12:30:00"),
        ("0.5208449074074074", "h:mm:ss.0", "12:30:01"),
        ("0.9999999884259259", "h:mm:ss.0", "23:59:59"),
        ("1", "h:mm:ss.0", None),
        ("-0.5", "h:mm:ss.0", None),
        ("0.5", "[h]:mm:ss.0", None),
        ("0.5", "h:mm:ss.0 AM/PM", None),
        ("44927.5", "yyyy-mm-dd h:mm:ss.0", None),
        ("0.5", "h:mm:ss.0000", None),
    ],
)
def test_time_formula_bar_scope(raw: str, code: str, expected: str | None) -> None:
    assert formula_bar_value(raw, code, "zh-CN") == expected
    assert formula_bar_value(raw, code, "en-US") is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ('[DBNum2]"-"General', "-壹仟贰佰叁拾肆"),
        ('[DBNum1]General;[Red][DBNum2]"("General")"', "(壹仟贰佰叁拾肆)"),
    ],
)
def test_chinese_negative_sections_preserve_sign_literals(code: str, expected: str) -> None:
    assert format_value(176, code, "-1234", date_1904=False, locale="zh-CN") == expected
    assert formula_bar_value("-1234", code, "zh-CN") == "-1234"
