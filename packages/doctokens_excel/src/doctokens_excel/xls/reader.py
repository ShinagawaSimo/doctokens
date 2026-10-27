"""Basic BIFF8 content extraction through shared CFB infrastructure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from
from typing import Literal

from doctokens_core.containers.cfb import CfbError, CfbReader
from doctokens_core.contracts.models import ParseWarning

from .cells import read_cells
from .formats import XlsFormatIndex
from .models import XlsContent, XlsError, XlsLimits, XlsSheet
from .records import Budget, Cursor, read_bof
from .strings import read_sst, short_string


@dataclass(frozen=True, slots=True)
class SheetRef:
    name: str
    offset: int
    state: Literal["visible", "hidden", "veryHidden"]
    kind: int


def _globals(cursor: Cursor, formats: XlsFormatIndex) -> tuple[list[SheetRef], list[str], bool]:
    read_bof(cursor, 0x0005)
    sheets: list[SheetRef] = []
    strings: list[str] = []
    seen_sst = False
    date_1904 = False
    names: set[str] = set()
    offsets: set[int] = set()
    while True:
        record = cursor.next()
        if record.kind == 0x000A:
            if any(sheet.offset < cursor.position or sheet.offset > cursor.stream.size - 4 for sheet in sheets):
                raise XlsError("XLS worksheet pointer is outside the sheet area")
            return sheets, strings, date_1904
        if record.kind == 0x002F:
            raise XlsError("Encrypted XLS workbooks are not supported")
        if record.kind == 0x0085:
            data = cursor.payload(record, 8)
            offset, hidden, kind = unpack_from("<IBB", data)
            name = short_string(data, 6)
            if not name or name.upper() in names or offset in offsets or hidden & 3 == 3:
                raise XlsError("Invalid or duplicate XLS sheet declaration")
            names.add(name.upper())
            offsets.add(offset)
            state: Literal["visible", "hidden", "veryHidden"] = ("visible", "hidden", "veryHidden")[hidden & 3]
            sheets.append(SheetRef(name, offset, state, kind))
            if len(sheets) > cursor.budget.limits.max_sheets:
                raise XlsError("XLS exceeds max_sheets")
        elif record.kind == 0x00FC:
            if seen_sst:
                raise XlsError("Multiple XLS shared-string tables")
            seen_sst = True
            strings = read_sst(cursor, record)
        elif record.kind == 0x0022:
            value = unpack_from("<H", cursor.payload(record, 2))[0]
            if value not in (0, 1):
                raise XlsError("Invalid XLS date system")
            date_1904 = bool(value)
        elif record.kind == 0x00E0:
            formats.add_xf(cursor.payload(record))
        elif record.kind == 0x041E:
            data = cursor.payload(record, 5)
            formats.add_format(data)
            cursor.budget.add_string(unpack_from("<H", data, 2)[0])


def read_xls_content(source: str | Path | bytes, *, limits: XlsLimits | None = None, locale: str = "zh-CN") -> XlsContent:
    """Read saved values and supported numeric display text from BIFF8.

    Source handles are closed before returning the immutable content result.
    Numbers remain numeric in value; display_text applies supported formats.
    """
    options = limits or XlsLimits()
    budget = Budget(options)
    formats = XlsFormatIndex(locale, options.max_xfs)
    warnings: list[ParseWarning] = []
    sheets: list[XlsSheet] = []
    try:
        with CfbReader(source, limits=options.cfb) as container:
            if container.has_root_stream("EncryptionInfo") and container.has_root_stream("EncryptedPackage"):
                raise XlsError("Encrypted OOXML is not a supported BIFF8 workbook")
            stream = container.open_root_stream("Workbook")
            references, strings, date_1904 = _globals(Cursor(stream, budget), formats)
            for sheet in references:
                if sheet.kind != 0:
                    warnings.append(ParseWarning("XLS_SHEET_TYPE_UNSUPPORTED", "Only ordinary worksheets are read", sheet.name))
                    continue
                cells = read_cells(Cursor(stream, budget, sheet.offset), strings, formats)
                if cells is None:
                    warnings.append(ParseWarning("XLS_SHEET_TYPE_UNSUPPORTED", "Dialog sheet is not read", sheet.name))
                    continue
                sheets.append(XlsSheet(sheet.name, sheet.state, cells))
            return XlsContent(tuple(sheets), date_1904, (*warnings, *formats.warnings))
    except CfbError as exc:
        raise XlsError(str(exc)) from exc
