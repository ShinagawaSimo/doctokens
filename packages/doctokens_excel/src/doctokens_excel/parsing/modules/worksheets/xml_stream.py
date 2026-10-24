"""Worksheet end events that release completed row nodes from sheetData."""

from __future__ import annotations

from collections.abc import Iterator
from typing import IO
from xml.etree import ElementTree as ET

from doctokens_core.xml import iterparse

from .sheet_types import NS_S

_ROW = f"{{{NS_S}}}row"
_SHEET_DATA = f"{{{NS_S}}}sheetData"


def iter_sheet_elements(stream: IO[bytes]) -> Iterator[ET.Element]:
    """Keep a row intact through its end event, then remove its parent link.

    Sheet declarations retain their existing complete-subtree lifetime. Start
    events track the sheetData parent only; callers still consume end events.
    """
    parent: ET.Element | None = None
    depth = parent_depth = 0
    for event, element in iterparse(stream, events=("start", "end")):
        if event == "start":
            depth += 1
            if element.tag == _SHEET_DATA:
                parent, parent_depth = element, depth
            continue
        yield element
        if element.tag == _ROW:
            element.clear()
            if parent is not None and depth == parent_depth + 1:
                parent.remove(element)
        elif element is parent:
            parent = None
        depth -= 1
