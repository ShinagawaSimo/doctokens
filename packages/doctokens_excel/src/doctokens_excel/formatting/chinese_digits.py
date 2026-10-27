"""Chinese Excel counting groups, shared by values and elapsed time."""

from __future__ import annotations

DBNUM_DIGITS = {"dbnum1": "○一二三四五六七八九", "dbnum2": "零壹贰叁肆伍陆柒捌玖", "dbnum3": "０１２３４５６７８９"}
DBNUM_UNITS = {"dbnum1": "十百千", "dbnum2": "拾佰仟", "dbnum3": "十百千"}


def translate_digits(text: str, mode: str) -> str:
    return text.translate(str.maketrans("0123456789", DBNUM_DIGITS[mode]))


def integer_text(value: int, digits: str, units: str) -> str:
    if value < 0:
        raise ValueError("Chinese counting groups require a nonnegative value")
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
        output.append(("", "万", "亿", "兆")[position])
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
