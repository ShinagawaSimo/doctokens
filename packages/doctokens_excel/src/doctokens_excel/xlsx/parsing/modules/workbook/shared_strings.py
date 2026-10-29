"""Decode shared strings one SI at a time without retaining the SST XML tree."""

from __future__ import annotations

from functools import partial
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.containers.opc.xml import iterparse
from doctokens_core.contracts.models import ParseWarning

from ....model.workbook import RichTextRun
from .string_text import read_string

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_SI = f"{{{_NS}}}si"
SharedStrings = list[str] | dict[int, str]


def _warning(warnings: list[ParseWarning], locator: str, code: str, message: str) -> None:
    warnings.append(ParseWarning(code, message, locator))


def _parse_shared_strings(
    package_reader: PackageReader,
    warnings: list[ParseWarning],
    *,
    include_rich_text: bool,
    needed_indices: set[int] | None = None,
) -> tuple[SharedStrings, dict[int, list[RichTextRun]]]:
    part = "xl/sharedStrings.xml"
    if not package_reader.exists(part):
        return [], {}
    strings: SharedStrings = [] if needed_indices is None else {}
    rich_map: dict[int, list[RichTextRun]] = {}
    root: ET.Element | None = None
    depth = 0
    index = 0
    with package_reader.open_entry(part) as stream:
        for event, element in iterparse(stream, events=("start", "end")):
            if event == "start":
                depth += 1
                if depth == 1:
                    root = element
                continue
            if depth == 2:
                if element.tag == _SI:
                    if needed_indices is None or index in needed_indices:
                        value, rich = read_string(
                            element,
                            rich=include_rich_text,
                            warn=partial(_warning, warnings, f"{part}:si[{index}]"),
                        )
                        if rich is not None:
                            rich_map[index] = rich
                        if isinstance(strings, dict):
                            strings[index] = value
                        else:
                            strings.append(value)
                    index += 1
                element.clear()
                if root is not None:
                    root.remove(element)
            depth -= 1
    return strings, rich_map
