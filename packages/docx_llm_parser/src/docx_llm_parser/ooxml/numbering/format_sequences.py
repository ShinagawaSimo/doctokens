"""Format sequences."""

from __future__ import annotations

from collections.abc import Sequence

from ooxml_llm_core.text_numbering import roman_number

from .format_codes import _HEBREW_ALPHABET


def _decimal_ordinal(value: int) -> str:
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _decimal_zero(value: int) -> str:
    return f"{value:02d}"


def _number_in_dash(value: int) -> str:
    return f"- {value} -"


def _custom(value: int) -> str:
    return str(value)


def _hexadecimal(value: int) -> str:
    return f"{value:X}" if 0 <= value <= 65_535 else str(value)


def _roman(value: int) -> str:
    return roman_number(value)


def _translate_digits(value: int, digits: str) -> str:
    if value < 0:
        return str(value)
    return "".join(digits[int(character)] if character.isdigit() else character for character in str(value))


def _chinese_digital(value: int) -> str:
    return _translate_digits(value, digits="〇一二三四五六七八九")


def _word_repeated_sequence(value: int, sequence: Sequence[str]) -> str:
    if value <= 0 or not sequence:
        return str(value)
    quotient, remainder = divmod(value - 1, len(sequence))
    return sequence[remainder] * (quotient + 1)


def _word_cycled_sequence(value: int, sequence: str) -> str:
    if value <= 0 or not sequence:
        return str(value)
    return sequence[(value - 1) % len(sequence)]


def _word_letter_sequence(value: int, sequence: str) -> str:
    return _word_repeated_sequence(value, sequence) if value <= len(sequence) * 30 else str(value)


def _arabic_sequence(value: int, sequence: str, prefix: str = "", suffix: str = "") -> str:
    return prefix + _word_repeated_sequence(value, sequence) + suffix


def _cycled_sequence(value: int, sequence: str) -> str:
    if value <= 0 or not sequence:
        return str(value)
    return sequence[(value - 1) % len(sequence)]


def _bounded_sequence(value: int, sequence: str) -> str:
    return sequence[value - 1] if 1 <= value <= len(sequence) else str(value)


def _enclosed_decimal(value: int, start: int, last: int) -> str:
    return chr(start + value - 1) if 1 <= value <= last else str(value)


def _ideograph_enclosed_circle(value: int) -> str:
    if 1 <= value <= 10:
        return f"({chr(0x3220 + value - 1)})"
    return str(value)


def _chinese_counting(value: int) -> str:
    if value < 0:
        return str(value)
    digits = "○一二三四五六七八九"
    if value <= 10:
        return digits[value] if value < 10 else "十"
    if value < 100:
        tens, ones = divmod(value, 10)
        prefix = "十" if tens == 1 else digits[tens] + "十"
        return prefix + ("" if not ones else digits[ones])
    return _translate_digits(value, digits=digits)


def _unit_counting(
    value: int,
    digits: str,
    units: str,
    *,
    zero: str,
    omit_one_ten: bool = True,
    omit_one_units: bool = False,
    insert_zero: bool = True,
) -> str:
    if value == 0:
        return digits[0]
    if value < 0:
        return str(value)

    parts: list[str] = []
    pending_zero = False
    remaining = value
    for divisor, unit in ((1000, units[2]), (100, units[1]), (10, units[0])):
        digit, remaining = divmod(remaining, divisor)
        if digit:
            if pending_zero and insert_zero:
                parts.append(zero)
            pending_zero = False
            omit_one = (divisor == 10 and omit_one_ten) or omit_one_units
            if not (digit == 1 and not parts and omit_one):
                parts.append(digits[digit])
            parts.append(unit)
        elif parts and remaining:
            pending_zero = True
    if remaining:
        if pending_zero and insert_zero:
            parts.append(zero)
        parts.append(digits[remaining])
    return "".join(parts)


def _korean_unit_counting(value: int) -> str:
    if value == 0:
        return "영"
    digits = "영일이삼사오육칠팔구"
    units = "십백천"
    if value < 10_000:
        return _unit_counting(
            value,
            digits,
            units,
            zero="영",
            omit_one_units=True,
            insert_zero=False,
        )
    high, low = divmod(value, 10_000)
    high_text = (
        ""
        if high == 1
        else _unit_counting(
            high,
            digits,
            units,
            zero="영",
            omit_one_units=True,
            insert_zero=False,
        )
    )
    result = high_text + "만"
    return (
        result
        if not low
        else result
        + _unit_counting(
            low,
            digits,
            units,
            zero="영",
            omit_one_units=True,
            insert_zero=False,
        )
    )


def _sexagenary_cycle(value: int) -> str:
    if value <= 0:
        return str(value)
    stems = "甲乙丙丁戊己庚辛壬癸"
    branches = "子丑寅卯辰巳午未申酉戌亥"
    index = (value - 1) % 60
    return stems[index % 10] + branches[index % 12]


def _hebrew_numeral(value: int) -> str:
    if value <= 0:
        return str(value)
    thousands, remainder = divmod(value, 1000)
    parts = _hebrew_numeral(thousands) if thousands else ""
    hundreds, remainder = divmod(remainder, 100)
    if hundreds:
        parts += "קרשתךםןףץ"[hundreds - 1]
    if remainder in {15, 16}:
        return parts + ("טו" if remainder == 15 else "טז")
    tens, units = divmod(remainder, 10)
    if tens:
        parts += "יכלמנסעפצ"[tens - 1]
    if units:
        parts += "אבגדהוזחט"[units - 1]
    return parts


def _hebrew_alphabet(value: int) -> str:
    if value <= 0:
        return str(value)
    quotient, remainder = divmod(value - 1, len(_HEBREW_ALPHABET))
    return "\u200f" + _HEBREW_ALPHABET[remainder] + "ת" * quotient


def _chicago(value: int) -> str:
    if value <= 0 or value > 116:
        return "" if value > 116 else str(value)
    symbols = "*†‡§"
    quotient, remainder = divmod(value - 1, len(symbols))
    return symbols[remainder] * (quotient + 1)
