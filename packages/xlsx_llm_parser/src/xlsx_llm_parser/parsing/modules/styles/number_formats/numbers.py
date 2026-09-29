"""Numbers."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction

from .codes import _date_scan_text
from .sections import _clean_display_pattern, _section_directives, _select_format_section, _split_format_sections


def _format_number_value(num: float, raw: str, fmt_code: str, is_pct: bool, locale: str) -> str:
    section, _selected_value = _select_format_section(num, fmt_code)
    if section is None:
        return raw
    magnitude = abs(Decimal(raw))
    _conditions, _currency, dbnum = _section_directives(section)
    syntax = _date_scan_text(section)
    if "@" in syntax and not re.search(r"[0#?]", syntax):
        return raw
    if dbnum:
        return raw

    magnitude *= Decimal(100) ** syntax.count("%")
    core_match = re.search(r"[0#?]", syntax)
    if core_match is None:
        return _clean_display_pattern(section)
    first = core_match.start()
    fraction_match = re.search(r"(?:[0#?]+\s+)?[0#?]+\s*/\s*(?:[1-9]\d*|[0#?]+)", syntax)
    if fraction_match:
        first = fraction_match.start()
        last = fraction_match.end() - 1
    else:
        last = max(index for index, char in enumerate(syntax) if char in "0#?")
        while last + 1 < len(syntax) and syntax[last + 1] == ",":
            last += 1
    prefix = _clean_display_pattern(section[:first])
    core = section[first : last + 1]
    suffix = _clean_display_pattern(section[last + 1 :])

    # Office accepts the uppercase ``E+``/``E-`` spellings for scientific
    # notation.  A lowercase ``e`` is ordinary literal text in a custom code
    # and must not silently trigger a scientific re-render.
    if re.fullmatch(r"[0#?]+(?:\.[0#?]+)?E[+-][0#?]+", core):
        rendered = _format_scientific(float(magnitude), core)
    elif re.search(r"e[+-][0#?]+", core):
        # MS-OI29500 records both spellings in the grammar, but Office's
        # display engine accepts only uppercase E markers.  Preserve the
        # lexical value for the unsupported lowercase form.
        return raw
    elif re.fullmatch(r"(?:[0#?]+\s+)?[0#?]+\s*/\s*(?:[1-9]\d*|[0#?]+)", core):
        rendered = _format_fraction(float(magnitude), core)
    elif re.fullmatch(r"[0#?,]+(?:\.[0#?]+)?,*", core):
        rendered = _format_decimal(magnitude, core)
    else:
        return raw
    if num < 0 and len(_split_format_sections(fmt_code)) == 1 and not _explicit_negative_prefix(section):
        rendered = "-" + rendered
    return prefix + rendered + suffix


def _explicit_negative_prefix(section: str) -> bool:
    """Whether a selected numeric section already writes its own sign."""
    cleaned = _clean_display_pattern(section)
    match = re.search(r"[0#?]", cleaned)
    prefix = cleaned if match is None else cleaned[: match.start()]
    return "-" in prefix or "(" in prefix


def _decimal_value(value: float | Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _format_decimal(value: float | Decimal, core: str) -> str:
    trailing_commas = len(core) - len(core.rstrip(","))
    core = core.rstrip(",")
    decimal_at = core.find(".")
    integer_pattern = core if decimal_at == -1 else core[:decimal_at]
    fraction_pattern = "" if decimal_at == -1 else core[decimal_at + 1 :]
    scale_commas = trailing_commas + len(integer_pattern) - len(integer_pattern.rstrip(","))
    integer_pattern = integer_pattern.rstrip(",")
    scaled = _decimal_value(value) / (Decimal(1000) ** scale_commas)
    decimal_places = sum(char in "0#?" for char in fraction_pattern)
    quantum = Decimal(1).scaleb(-decimal_places)
    quantized = scaled.quantize(quantum, rounding=ROUND_HALF_UP)
    text_value = f"{quantized:f}"
    integer, _, fraction = text_value.partition(".")
    min_integer = integer_pattern.count("0")
    if integer == "0" and min_integer == 0 and "0" not in integer_pattern:
        integer = ""
    integer = integer.rjust(min_integer, "0")
    if "," in integer_pattern and integer:
        chunks: list[str] = []
        while integer:
            chunks.insert(0, integer[-3:])
            integer = integer[:-3]
        integer = ",".join(chunks)
    elif "?" in integer_pattern:
        integer = integer.rjust(sum(char in "0?" for char in integer_pattern), " ")
    if fraction_pattern:
        fraction = fraction.ljust(decimal_places, "0")
        digits = list(fraction)
        for index in range(len(digits) - 1, -1, -1):
            if digits[index] != "0" or fraction_pattern[index] == "0":
                break
            digits[index] = " " if fraction_pattern[index] == "?" else ""
        fraction = "".join(digits)
        return integer + ("." + fraction if fraction else "")
    return integer


def _format_scientific(value: float, core: str) -> str:
    match = re.search(r"([0#?]+)(?:\.([0#?]+))?E([+-])([0#?]+)", core)
    if match is None:
        return str(value)
    mantissa_pattern = match.group(1) + ("." + match.group(2) if match.group(2) else "")
    exponent = 0 if value == 0 else math.floor(math.log10(abs(value)))
    integer_places = len(match.group(1))
    exponent -= exponent % integer_places
    mantissa = value / (10**exponent) if value else 0.0
    rendered = _format_decimal(abs(mantissa), mantissa_pattern)
    # Rounding a mantissa such as 9.999 to a two-place pattern can carry it
    # to 10.00.  Normalize the exponent after that carry so the rendered
    # scientific value remains equivalent to the source number.
    try:
        if float(rendered) >= 10**integer_places:
            exponent += integer_places
            mantissa /= 10**integer_places
            rendered = _format_decimal(abs(mantissa), mantissa_pattern)
    except ValueError:
        pass
    sign = "+" if exponent >= 0 else "-"
    width = len(match.group(4))
    exponent_text = str(abs(exponent)).rjust(width, "0")
    return f"{rendered}E{sign if match.group(3) == '+' or exponent < 0 else ''}{exponent_text}"


def _format_fraction(value: float, core: str) -> str:
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
    denominator_width = len(denominator_pattern) or len(denominator_literal)
    denominator_limit = fixed_denominator if fixed_denominator is not None else 10 ** max(1, len(denominator_pattern)) - 1
    denominator_limit = max(1, min(denominator_limit, 999))

    magnitude = abs(value)
    whole_value = math.floor(magnitude)
    remainder_value = magnitude - whole_value if whole_pattern else magnitude
    if fixed_denominator is not None:
        denominator_value = fixed_denominator
        numerator_value = int((Decimal(str(remainder_value)) * denominator_value).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if whole_pattern and numerator_value >= denominator_value:
            whole_value += 1
            numerator_value = 0
        whole = str(whole_value) if whole_pattern else ""
        remainder = numerator_value
    else:
        fraction = Fraction(magnitude).limit_denominator(denominator_limit)
        whole_value = fraction.numerator // fraction.denominator
        whole = str(whole_value) if whole_pattern else ""
        remainder = fraction.numerator % fraction.denominator if whole_pattern else fraction.numerator
        denominator_value = fraction.denominator

    if whole_value == 0 and (not whole_pattern or set(whole_pattern) <= {"#", "?"}):
        whole = ""
    numerator = _fraction_placeholder(str(remainder), numerator_pattern)
    denominator = (
        str(denominator_value)
        if fixed_denominator is not None
        else _fraction_placeholder(str(denominator_value), denominator_pattern, literal_width=denominator_width)
    )
    if remainder == 0:
        return whole
    if whole:
        return f"{whole} {numerator}/{denominator}"
    return f"{numerator}/{denominator}"


def _fraction_placeholder(value: str, pattern: str, *, literal_width: int = 0) -> str:
    """Apply fraction placeholder padding without turning ``?`` into zero.

    In an Excel format code, ``0`` reserves a visible zero while ``?``
    reserves a blank position.  The old implementation padded every
    numerator and denominator with ``0``, which made ``# ??/??`` render
    ``01/04`` instead of the Office-style space-padded fraction.
    """
    width = max(1, len(pattern) or literal_width)
    if len(value) >= width:
        return value
    if "0" in pattern:
        return value.rjust(width, "0")
    if "?" in pattern:
        return value.rjust(width, " ")
    return value
