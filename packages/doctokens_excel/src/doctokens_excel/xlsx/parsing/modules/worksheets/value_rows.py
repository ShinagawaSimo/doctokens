"""Resumable display-only rows, detaching completed XML rows immediately."""

from __future__ import annotations

from collections.abc import Iterator
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.reader import PackageReader
from doctokens_core.containers.opc.xml import iterparse
from doctokens_core.runtime.execution import checkpoint

from ....model.workbook import Cell
from ...plan import XlsxParsePlan
from ..styles.index import FormatIndex
from ..workbook.rich_values import RichValueCatalog
from ..workbook.shared_strings import SharedStrings
from .cells import _row_attrs
from .scanner import WorksheetScanner
from .sheet_post_index import SheetPostIndex
from .sheet_types import NS_S
from .working_set import SheetWorkingSet


def iter_value_rows(package: PackageReader, part: str, strings: SharedStrings, formats: FormatIndex) -> Iterator[list[Cell]]:
    cells: list[Cell] = []

    def consume(_number: int, row: list[Cell]) -> bool:
        nonlocal cells
        cells = row
        return True

    scanner = WorksheetScanner(
        package, part, strings, None, formats, [], {}, RichValueCatalog(), XlsxParsePlan.values(""), None, consume
    )
    working, post = SheetWorkingSet(scanner.flags), SheetPostIndex(scanner.flags)
    parent: ET.Element | None = None
    previous = 0
    inside_row = False
    with package.open_entry(part) as stream:
        for event, element in iterparse(stream, events=("start", "end")):
            if event == "start":
                if element.tag == f"{{{NS_S}}}sheetData":
                    parent = element
                if element.tag == f"{{{NS_S}}}row":
                    inside_row = True
                continue
            if element.tag != f"{{{NS_S}}}row":
                if not inside_row and element is not parent:
                    element.clear()
                continue
            checkpoint("searching worksheet rows")
            attrs = _row_attrs(element)
            previous = attrs.number or previous + 1
            scanner._read_row(element, attrs._replace(number=previous), working, post)
            post.blank_content_refs.clear()
            element.clear()
            if parent is not None:
                parent.remove(element)
            inside_row = False
            yield cells
