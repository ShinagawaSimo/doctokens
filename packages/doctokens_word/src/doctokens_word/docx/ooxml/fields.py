"""Read navigation from saved Word fields without evaluating their results."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..model import FieldInfo, LinkInfo, Run

_ARGUMENT_SWITCHES = {
    "HYPERLINK": {"l", "o", "t"},
    "REF": {"d"},
    "PAGEREF": set(),
    "NOTEREF": set(),
    "CITATION": {"l", "m", "p", "s", "v", "f"},
}
_FLAG_SWITCHES = {
    "HYPERLINK": {"m", "n"},
    "REF": {"f", "h", "n", "p", "r", "t", "w"},
    "PAGEREF": {"h", "p"},
    "NOTEREF": {"f", "h", "p"},
    "CITATION": {"n", "t", "y"},
}


@dataclass(frozen=True)
class _Token:
    value: str
    switch: bool = False


def _tokenize(instruction: str) -> list[_Token]:
    """Recognize Word quotes, escaped quotes/backslashes, and adjacent switches."""
    tokens: list[_Token] = []
    index = 0
    while index < len(instruction):
        char = instruction[index]
        if char.isspace():
            index += 1
            continue
        if char == "\\" and index + 1 < len(instruction) and instruction[index + 1] not in {'"', "\\"}:
            tokens.append(_Token(instruction[index + 1].lower(), switch=True))
            index += 2
            continue
        quoted = char == '"'
        if quoted:
            index += 1
        value: list[str] = []
        while index < len(instruction):
            char = instruction[index]
            if char == "\\" and index + 1 < len(instruction) and instruction[index + 1] in {'"', "\\"}:
                value.append(instruction[index + 1])
                index += 2
                continue
            if quoted and char == '"':
                index += 1
                break
            if not quoted and (char.isspace() or char in {'"', "\\"}):
                break
            value.append(char)
            index += 1
        else:
            if quoted:
                raise ValueError("Unclosed quoted field argument")
        if not quoted and not value:
            raise ValueError("Incomplete field escape")
        tokens.append(_Token("".join(value)))
    return tokens


def _field_metadata(tokens: list[_Token]) -> tuple[LinkInfo, FieldInfo] | None:
    if not tokens:
        return None
    kind = tokens[0].value.upper()
    if kind not in _ARGUMENT_SWITCHES or tokens[0].switch:
        return None
    positional: list[str] = []
    switches: dict[str, str] = {}
    index = 1
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token.switch:
            positional.append(token.value)
            continue
        if token.value in _ARGUMENT_SWITCHES[kind] | {"*", "#", "@"}:
            if index == len(tokens) or tokens[index].switch:
                raise ValueError(f"Missing argument for field switch \\{token.value}")
            switches[token.value] = tokens[index].value
            index += 1
        elif token.value not in _FLAG_SWITCHES[kind]:
            raise ValueError(f"Unsupported field switch \\{token.value}")
    if len(positional) > 1:
        raise ValueError("Ambiguous field arguments")
    target = positional[0] if positional else ""
    if kind == "CITATION":
        return ({}, {"kind": "citation", "key": target}) if target else None
    anchor = switches.get("l", "") if kind == "HYPERLINK" else target
    link: LinkInfo = {}
    if kind == "HYPERLINK" and target:
        link["href"] = target
    if anchor:
        link["anchor"] = anchor
    return (link, {"kind": "reference", "anchor": anchor}) if link else None


def apply_field_instruction(instruction: str, result_runs: list[Run], warn: Callable[[str, str], None]) -> None:
    """Annotate cached results; malformed or unsupported syntax never invents a target."""
    if not result_runs or not instruction.strip():
        return
    keyword = re.match(r"\s*([A-Za-z]+)", instruction)
    if keyword is None or keyword[1].upper() not in _ARGUMENT_SWITCHES:
        return
    try:
        metadata = _field_metadata(_tokenize(instruction))
    except ValueError as exc:
        warn("INVALID_FIELD_INSTRUCTION", str(exc))
        return
    if metadata is None:
        return
    link, field = metadata
    for run in result_runs:
        if link:
            run["link"] = link.copy()
        run["field"] = field.copy()
