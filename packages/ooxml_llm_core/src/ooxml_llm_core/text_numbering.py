"""Shared text auto-numbering conversions used by DrawingML consumers."""

from __future__ import annotations


def alpha_number(number: int, *, upper: bool) -> str:
    """Convert a positive number to the DrawingML alphabetic sequence."""
    if number <= 0:
        return str(number)
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr((65 if upper else 97) + remainder) + result
    return result


def roman_number(number: int) -> str:
    """Convert a positive number to additive/subtractive Roman numerals."""
    if number <= 0:
        return str(number)
    values = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result: list[str] = []
    for value, token in values:
        count, number = divmod(number, value)
        result.append(token * count)
    return "".join(result)


def format_drawingml_autonumber(number: int, scheme: str) -> str:
    """Render a DrawingML ``a:buAutoNum`` value.

    The shared layer owns only scheme-to-visible-text conversion. The caller
    owns paragraph scope, level counters, inheritance, and ``startAt``.
    Unsupported schemes retain the decimal-period fallback.
    """
    if scheme == "alphaLcParenBoth":
        return f"({alpha_number(number, upper=False)})"
    if scheme in {"alphaLcParenR", "alphaLcParenRight"}:
        return f"{alpha_number(number, upper=False)})"
    if scheme == "alphaLcPeriod":
        return f"{alpha_number(number, upper=False)}."
    if scheme == "alphaUcParenBoth":
        return f"({alpha_number(number, upper=True)})"
    if scheme in {"alphaUcParenR", "alphaUcParenRight"}:
        return f"{alpha_number(number, upper=True)})"
    if scheme == "alphaUcPeriod":
        return f"{alpha_number(number, upper=True)}."

    if scheme == "romanLcParenBoth":
        return f"({roman_number(number).lower()})"
    if scheme in {"romanLcParenR", "romanLcParenRight"}:
        return f"{roman_number(number).lower()})"
    if scheme == "romanLcPeriod":
        return f"{roman_number(number).lower()}."
    if scheme == "romanUcParenBoth":
        return f"({roman_number(number)})"
    if scheme in {"romanUcParenR", "romanUcParenRight"}:
        return f"{roman_number(number)})"
    if scheme == "romanUcPeriod":
        return f"{roman_number(number)}."

    if scheme == "arabicParenBoth":
        return f"({number})"
    if scheme in {"arabicParenR", "arabicParenRight"}:
        return f"{number})"
    if scheme in {"arabicPlain", "arabic1Minus", "arabic2Minus", "hebrew2Minus"}:
        return str(number)
    if scheme == "arabicDbPlain":
        return _full_width_digits(number)
    if scheme == "arabicDbPeriod":
        return f"{_full_width_digits(number)}．"
    if scheme == "circleNumDbPlain":
        return chr(0x2460 + number - 1) if 1 <= number <= 10 else str(number)
    if scheme in {"arabicPeriod", "ea1ChsPeriod", "ea1ChtPeriod", "ea1JpnChsDbPeriod", "ea1JpnKorPeriod"}:
        return f"{number}."
    return f"{number}."


def _full_width_digits(number: int) -> str:
    digits = "０１２３４５６７８９"
    return "".join(digits[int(char)] if char.isdigit() else char for char in str(number))


__all__ = ["alpha_number", "format_drawingml_autonumber", "roman_number"]
