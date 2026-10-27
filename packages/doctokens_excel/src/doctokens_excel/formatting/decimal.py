"""Decimal placeholders with embedded literals and explicit alignment rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from .sections import currency_parts


def pattern_tokens(pattern: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == '"':
            end = pattern.find('"', index + 1)
            if end < 0:
                raise ValueError("Unclosed format literal")
            tokens.append(("literal", pattern[index + 1 : end]))
            index = end + 1
        elif char in "\\_*":
            if index + 1 >= len(pattern):
                raise ValueError("Missing escaped format character")
            if char != "*":
                tokens.append(("literal", pattern[index + 1] if char == "\\" else " "))
            index += 2
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end < 0:
                raise ValueError("Unclosed format directive")
            directive = pattern[index + 1 : end]
            if directive.startswith("$"):
                symbol, _language = currency_parts(directive[1:])
                tokens.append(("literal", symbol or ""))
            index = end + 1
        else:
            tokens.append(("syntax" if char in "0#?.,%" else "literal", char))
            index += 1
    return tokens


@dataclass(frozen=True, slots=True)
class DecimalPattern:
    tokens: tuple[tuple[str, str], ...]
    decimal: int
    integers: tuple[int, ...]
    fractions: tuple[int, ...]
    scale: int
    grouping: bool


def compile_decimal_pattern(pattern: str) -> DecimalPattern:
    tokens = tuple(pattern_tokens(pattern))
    if tokens.count(("syntax", ".")) > 1:
        raise ValueError("Multiple decimal points in a numeric pattern")
    decimal = next((i for i, token in enumerate(tokens) if token == ("syntax", ".")), len(tokens))
    integer_slots = tuple(i for i, (kind, text) in enumerate(tokens[:decimal]) if kind == "syntax" and text in "0#?")
    fraction_slots = tuple(i for i, (kind, text) in enumerate(tokens) if i > decimal and kind == "syntax" and text in "0#?")
    last = max(integer_slots + fraction_slots)
    scale = sum(token == ("syntax", ",") for token in tokens[last + 1 :])
    if decimal < len(tokens):
        tail = decimal - 1
        while tail >= 0 and tokens[tail] == ("syntax", ","):
            scale += 1
            tail -= 1
    grouping = any(tokens[i] == ("syntax", ",") for i in range(min(integer_slots, default=0), max(integer_slots, default=0)))
    return DecimalPattern(tokens, decimal, integer_slots, fraction_slots, scale, grouping)


def format_decimal_pattern(value: Decimal, pattern: str | DecimalPattern, *, digits: str | None = None) -> str:
    compiled = compile_decimal_pattern(pattern) if isinstance(pattern, str) else pattern
    tokens, decimal = compiled.tokens, compiled.decimal
    integer_slots, fraction_slots = compiled.integers, compiled.fractions
    with localcontext() as context:
        context.prec = max(32, abs(value.adjusted()) + len(fraction_slots) + len(value.as_tuple().digits) + 4)
        scaled = value / Decimal(1000) ** compiled.scale
        rounded = scaled.quantize(Decimal(1).scaleb(-len(fraction_slots)), rounding=ROUND_HALF_UP)
    integer, _, fraction = format(rounded, "f").partition(".")
    filled: dict[int, str] = {}
    integer_digits = list(integer if integer != "0" or any(tokens[i][1] == "0" for i in integer_slots) else "")
    for slot in reversed(integer_slots):
        if integer_digits:
            filled[slot] = integer_digits.pop()
        else:
            filled[slot] = {"0": "0", "?": " ", "#": ""}[tokens[slot][1]]
    if integer_digits:
        first = integer_slots[0] if integer_slots else decimal
        filled[first] = "".join(integer_digits) + filled.get(first, "")
    optional = True
    for offset in range(len(fraction_slots) - 1, -1, -1):
        slot = fraction_slots[offset]
        digit = fraction[offset]
        placeholder = tokens[slot][1]
        if optional and digit == "0" and placeholder != "0":
            filled[slot] = " " if placeholder == "?" else ""
        else:
            optional = False
            filled[slot] = digit
    # Group the emitted integer digits without treating embedded literal
    # punctuation or alignment spaces as numeric digits.
    if compiled.grouping:
        remaining = sum(len(filled.get(i, "").strip()) for i in integer_slots)
        for slot in integer_slots:
            text = filled[slot]
            grouped = []
            for char in text:
                if char.isdigit():
                    remaining -= 1
                grouped.append(char)
                if char.isdigit() and remaining and remaining % 3 == 0:
                    grouped.append(",")
            filled[slot] = "".join(grouped)
    if digits is not None:
        table = str.maketrans("0123456789", digits)
        filled = {slot: text.translate(table) for slot, text in filled.items()}
    output: list[str] = []
    for index, (kind, text) in enumerate(tokens):
        if index in filled:
            output.append(filled[index])
        if kind == "literal":
            output.append(text)
        elif text == ".":
            output.append(".")
        elif text == "%":
            output.append(text)
    return "".join(output)
