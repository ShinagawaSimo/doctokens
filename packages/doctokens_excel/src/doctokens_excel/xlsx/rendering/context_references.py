"""Saved reference evidence for range context; no formula evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..model.coordinates import _col_from_str
from .selection import MAX_COLUMN, MAX_ROW, parse_range

Bounds = tuple[int, int, int, int]
_SHEET = r"(?:'(?:[^']|'')+'|(?:\[[^\]]+\])?[\w.\\]+)"
_QUALIFIER = rf"(?P<sheet>{_SHEET})!"
_QUALIFIED_SHEET = re.compile(rf"{_SHEET}!")
_CELL = r"\$?[A-Za-z]{1,3}\$?[1-9][0-9]*"
_AREA = rf"{_CELL}(?:\s*:\s*{_CELL})?|\$?[A-Za-z]{{1,3}}:\$?[A-Za-z]{{1,3}}|\$?[1-9][0-9]*:\$?[1-9][0-9]*"
_REFERENCE = re.compile(rf"(?<![\w.\\])(?:{_QUALIFIER})?(?P<area>{_AREA})(?![\w.\[]|\s*\()")
_NAME = re.compile(rf"(?<![\w.\\])(?:{_QUALIFIER})?(?P<name>(?!\d)[\w\\][\w.\\]*)(?![\w.\\])")
_STRING = re.compile(r'"(?:[^"]|"")*"')


def _without_column_labels(source: str) -> str:
    """Hide structured labels before recognizing A1-like column names."""
    parts: list[str] = []
    index = 0
    while index < len(source):
        if source[index] in "'[" and (qualifier := _QUALIFIED_SHEET.match(source, index)):
            end = qualifier.end()
            parts.append(source[index:end])
        elif source[index] == "[":
            end, depth = index + 1, 1
            while end < len(source) and depth:
                if source[end] == "'" and end + 1 < len(source) and source[end + 1] in "[]'#@":
                    end += 2
                    continue
                depth += (source[end] == "[") - (source[end] == "]")
                end += 1
            parts.append(" " * (end - index))
        else:
            end = index + 1
            parts.append(source[index])
        index = end
    return "".join(parts)


def area_bounds(value: str) -> Bounds | None:
    value = re.sub(r"\s", "", value).replace("$", "")
    if columns := re.fullmatch(r"([A-Za-z]{1,3}):([A-Za-z]{1,3})", value):
        left, right = (_col_from_str(col.upper()) for col in columns.groups())
        return (left, 1, right, MAX_ROW) if 1 <= left <= right <= MAX_COLUMN else None
    try:
        return parse_range(value)
    except ValueError:
        return None


def intersects(first: Bounds, second: Bounds) -> bool:
    return first[0] <= second[2] and second[0] <= first[2] and first[1] <= second[3] and second[1] <= first[3]


def relevant_range(ref: str, selected: Bounds) -> bool:
    """Unknown placement cannot prove an existing declaration unrelated."""
    areas = ref.split()
    return not areas or any((bounds := area_bounds(area)) is None or intersects(bounds, selected) for area in areas)


def _sheet_name(value: str | None) -> str | None:
    if value and value.startswith("'"):
        value = value[1:-1].replace("''", "'")
    return value.casefold() if value else None


@dataclass
class References:
    areas: list[tuple[str | None, Bounds]] = field(default_factory=list)
    names: set[tuple[str | None, str]] = field(default_factory=set)
    external: set[str] = field(default_factory=set)


def references(expression: str) -> References:
    """Recognize explicit A1/name/table references, excluding quoted text."""
    result = References()
    source = _without_column_labels(_STRING.sub(lambda match: " " * len(match[0]), expression))
    for qualifier in re.finditer(rf"{_SHEET}!", source):
        result.external.update(
            match[1] for match in re.finditer(r"\[([^\]]+\.(?:xlsx|xlsm|xlsb|xls|xltx|xltm|xlam|xla))\]", qualifier[0], re.I)
        )

    def area(match: re.Match[str]) -> str:
        if (bounds := area_bounds(match["area"])) is not None:
            result.areas.append((_sheet_name(match["sheet"]), bounds))
            return " " * len(match[0])
        return match[0]

    source = _REFERENCE.sub(area, source)
    for match in _NAME.finditer(source):
        if not source[match.end() :].lstrip().startswith("("):
            result.names.add((_sheet_name(match["sheet"]), match["name"].casefold()))
    return result
