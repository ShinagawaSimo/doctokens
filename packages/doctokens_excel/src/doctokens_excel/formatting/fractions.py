"""Bounded rational approximation and fixed-denominator reading text."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction


def format_fraction(value: Decimal, core: str) -> str:
    before, after = core.split("/", 1)
    before_parts = before.strip().split()
    if len(before_parts) >= 2:
        whole_pattern = re.sub(r"[^0#?]", "", before_parts[0])
        numerator_pattern = re.sub(r"[^0#?]", "", "".join(before_parts[1:]))
    else:
        whole_pattern = ""
        numerator_pattern = re.sub(r"[^0#?]", "", before)

    denominator_literal = after.strip()
    fixed_denominator = int(denominator_literal) if re.fullmatch(r"[1-9]\d*", denominator_literal) else None
    denominator_pattern = re.sub(r"[^0#?]", "", after)
    denominator_limit = fixed_denominator if fixed_denominator is not None else 10 ** max(1, len(denominator_pattern)) - 1
    denominator_limit = max(1, denominator_limit)

    magnitude = abs(value)
    whole_value = math.floor(magnitude)
    remainder_value = magnitude - whole_value if whole_pattern else magnitude
    if fixed_denominator is not None:
        denominator_value = fixed_denominator
        numerator_value = int((remainder_value * denominator_value).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if whole_pattern and numerator_value >= denominator_value:
            whole_value += 1
            numerator_value = 0
        whole = _fraction_placeholder(str(whole_value), whole_pattern) if whole_pattern else ""
        remainder = numerator_value
    else:
        fraction = Fraction(magnitude).limit_denominator(denominator_limit)
        whole_value = fraction.numerator // fraction.denominator
        whole = _fraction_placeholder(str(whole_value), whole_pattern) if whole_pattern else ""
        remainder = fraction.numerator % fraction.denominator if whole_pattern else fraction.numerator
        denominator_value = fraction.denominator

    if whole_value == 0 and (not whole_pattern or set(whole_pattern) <= {"#", "?"}):
        whole = ""
    numerator = _fraction_placeholder(str(remainder), numerator_pattern)
    denominator = (
        str(denominator_value)
        if fixed_denominator is not None
        else _fraction_placeholder(str(denominator_value), denominator_pattern)
    )
    if remainder == 0 and whole_pattern:
        return whole or "0"
    if whole:
        return f"{whole} {numerator}/{denominator}"
    return f"{numerator}/{denominator}"


def _fraction_placeholder(value: str, pattern: str) -> str:
    """Keep required zeroes, but omit width-only fraction alignment blanks.

    Numerator/denominator ``?`` positions align fractions visually in Excel;
    they are not spaces inside the textual value (``# ??/??`` gives ``1/4``).
    A mixed fraction still retains the separator after its whole-number part.
    """
    required_width = len(pattern) - pattern.index("0") if "0" in pattern else 0
    return value.zfill(required_width)
