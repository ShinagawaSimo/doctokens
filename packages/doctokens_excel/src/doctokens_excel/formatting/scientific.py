"""Decimal scientific and engineering notation without binary scaling overflow."""

from __future__ import annotations

import re
from decimal import Decimal, localcontext

from .decimal import format_decimal_pattern


def format_scientific(value: Decimal, core: str) -> str:
    match = re.fullmatch(r"([0#?]+)(?:\.([0#?]+))?E([+-])([0#?]+)", core)
    if match is None:
        raise ValueError("Unsupported scientific pattern")
    mantissa_pattern = match.group(1) + ("." + match.group(2) if match.group(2) else "")
    integer_places = len(match.group(1))
    exponent = value.adjusted() if value else 0
    exponent -= exponent % integer_places
    with localcontext() as context:
        context.prec = max(32, len(value.as_tuple().digits) + len(core) + 4)
        mantissa = value.scaleb(-exponent) if value else Decimal(0)
        rendered = format_decimal_pattern(mantissa, mantissa_pattern)
        if Decimal(rendered) >= Decimal(10) ** integer_places:
            exponent += integer_places
            mantissa /= Decimal(10) ** integer_places
            rendered = format_decimal_pattern(mantissa, mantissa_pattern)
    sign = "+" if exponent >= 0 else "-"
    width = len(match.group(4))
    exponent_text = str(abs(exponent)).zfill(width)
    return f"{rendered}E{sign if match.group(3) == '+' or exponent < 0 else ''}{exponent_text}"
