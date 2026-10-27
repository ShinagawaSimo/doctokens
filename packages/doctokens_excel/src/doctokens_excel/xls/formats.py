"""BIFF8 XF/Format decoding and source-independent numeric display selection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from struct import unpack_from

from doctokens_core.contracts.models import ParseWarning

from doctokens_excel.formatting.numeric import format_numeric_value
from doctokens_excel.formatting.program import FormatProgram
from doctokens_excel.formatting.values import builtin_format_code

from .models import XlsCell, XlsError

# MS-XLS 2.4.126 permits these localized built-ins and custom identifiers.
_FORMAT_IDS = frozenset((*range(5, 9), *range(23, 27), *range(41, 45), *range(63, 67), *range(164, 393)))
# Currency/accounting built-ins require the saved locale-dependent Format code.
_FIXED_BUILTINS = frozenset((*range(5), *range(9, 23), *range(37, 41), *range(45, 50)))


def read_number_format(data: bytes) -> tuple[int, str]:
    if len(data) < 5:
        raise XlsError("Truncated XLS Format record")
    identifier, count, flags = unpack_from("<HHB", data)
    if identifier not in _FORMAT_IDS or not 1 <= count <= 255:
        raise XlsError("Invalid XLS Format identifier or string length")
    width = 2 if flags & 1 else 1
    if len(data) != 5 + count * width:
        raise XlsError("Invalid XLS Format string byte length")
    try:
        return identifier, data[5:].decode("utf-16le" if width == 2 else "latin1")
    except UnicodeDecodeError as exc:
        raise XlsError("Invalid UTF-16 XLS Format string") from exc


@dataclass(frozen=True, slots=True)
class Xf:
    format_id: int
    is_style: bool
    parent: int


def read_xf(data: bytes) -> Xf:
    if len(data) != 20:
        raise XlsError("BIFF8 XF records must contain 20 bytes")
    format_id, flags = unpack_from("<HH", data, 2)
    if format_id > 392:
        raise XlsError("Invalid XLS XF number-format identifier")
    return Xf(format_id, bool(flags & 4), flags >> 4)


class XlsFormatIndex:
    def __init__(self, locale: str, max_xfs: int) -> None:
        self.locale = locale
        self.max_xfs = max_xfs
        self._xfs: list[Xf] = []
        self._codes: dict[int, str] = {}
        self._programs: dict[int, FormatProgram | None] = {}
        self._warned: set[int] = set()
        self.warnings: list[ParseWarning] = []

    def add_xf(self, data: bytes) -> None:
        if len(self._xfs) >= self.max_xfs:
            raise XlsError("XLS exceeds max_xfs")
        self._xfs.append(read_xf(data))

    def add_format(self, data: bytes) -> None:
        identifier, code = read_number_format(data)
        if identifier in self._codes:
            raise XlsError("Duplicate XLS Format identifier")
        self._codes[identifier] = code

    def _program(self, index: int) -> tuple[int, FormatProgram | None]:
        if not 0 <= index < len(self._xfs):
            raise XlsError(f"XLS cell references missing XF {index}")
        xf = self._xfs[index]
        if xf.is_style:
            raise XlsError("XLS cell references a style XF instead of a cell XF")
        if not 0 <= xf.parent < len(self._xfs) or not self._xfs[xf.parent].is_style:
            raise XlsError("XLS cell XF references an invalid parent style XF")
        # CellXF.fAtrNum controls updates when a style changes, not a request
        # to replace the saved ifmt with its parent's during read-only display.
        identifier = xf.format_id
        if identifier not in self._programs:
            code = self._codes.get(identifier)
            if code is None and identifier in _FIXED_BUILTINS:
                code = builtin_format_code(identifier, self.locale)
            if code is None and identifier >= 164:
                raise XlsError(f"Missing XLS Format record for identifier {identifier}")
            self._programs[identifier] = FormatProgram(code, self.locale) if code else None
        return identifier, self._programs[identifier]

    def format_cell(self, cell: XlsCell) -> XlsCell:
        identifier, program = self._program(cell.xf_index)
        text = str(cell.value)
        if cell.kind == "boolean":
            text = "TRUE" if cell.value else "FALSE"
        if cell.kind != "number" or identifier == 0:
            return replace(cell, display_text=text)
        rendered = format_numeric_value(text, program) if program is not None else None
        if rendered is None and identifier not in self._warned:
            self._warned.add(identifier)
            self.warnings.append(
                ParseWarning(
                    "XLS_NUMBER_FORMAT_UNSUPPORTED",
                    "Number format is not rendered; the saved numeric value is retained",
                    f"Workbook/Format[{identifier}]",
                )
            )
        return replace(cell, display_text=rendered if rendered is not None else text)
