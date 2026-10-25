"""BIFF8 Unicode and owner-aware SST/String continuation state."""

from __future__ import annotations

from struct import unpack_from

from doctokens_core.execution import checkpoint

from .models import XlsError
from .records import Cursor, Record


def short_string(data: bytes, offset: int) -> str:
    if len(data) < offset + 2:
        raise XlsError("Truncated BIFF short Unicode string")
    count, flags = data[offset : offset + 2]
    width = 2 if flags & 1 else 1
    end = offset + 2 + count * width
    if end != len(data):
        raise XlsError("Invalid BIFF short Unicode string length")
    try:
        return data[offset + 2 : end].decode("utf-16le" if width == 2 else "latin1")
    except UnicodeDecodeError as exc:
        raise XlsError("Invalid BIFF short Unicode string") from exc


class Segments:
    def __init__(self, cursor: Cursor, record: Record, offset: int = 0) -> None:
        self.cursor = cursor
        self.data = cursor.payload(record)
        self.position = offset

    def _continue(self, *, characters: bool = False) -> bool:
        if self.cursor.peek().kind != 0x003C:
            raise XlsError("Missing Continue record inside XLS string")
        self.data = self.cursor.payload(self.cursor.next(), 1)
        self.position = 0
        if characters:
            wide = bool(self.data[0] & 1)
            self.position = 1
            return wide
        return False

    def header(self, size: int, *, next_record: bool = True) -> bytes:
        if self.position == len(self.data) and next_record:
            self._continue()
        if size > len(self.data) - self.position:
            raise XlsError("XLS string header crosses a record boundary")
        value = self.data[self.position : self.position + size]
        self.position += size
        return value

    def skip(self, size: int) -> None:
        while size:
            checkpoint("skipping XLS string annotations")
            if self.position == len(self.data):
                self._continue()
            take = min(size, len(self.data) - self.position)
            self.position += take
            size -= take

    def characters(self, count: int, wide: bool) -> str:
        self.cursor.budget.add_string(count)
        parts: list[bytes] = []
        while count:
            checkpoint("decoding XLS strings")
            if self.position == len(self.data):
                wide = self._continue(characters=True)
            width = 2 if wide else 1
            take = min(count, (len(self.data) - self.position) // width)
            if not take:
                raise XlsError("Truncated UTF-16 code unit in XLS string")
            value = self.data[self.position : self.position + take * width]
            if not wide:
                expanded = bytearray(take * 2)
                expanded[::2] = value
                value = bytes(expanded)
            parts.append(value)
            self.position += take * width
            count -= take
        try:
            return b"".join(parts).decode("utf-16le")
        except UnicodeDecodeError as exc:
            raise XlsError("Invalid UTF-16 XLS string") from exc

    def finish(self) -> None:
        if self.position != len(self.data) or self.cursor.peek().kind == 0x003C:
            raise XlsError("Unexpected trailing data in XLS string record")


def read_sst(cursor: Cursor, record: Record) -> list[str]:
    segments = Segments(cursor, record)
    total, unique = unpack_from("<II", segments.header(8))
    if unique > cursor.budget.limits.max_strings or total < unique:
        raise XlsError("Invalid or over-budget XLS shared-string count")
    strings: list[str] = []
    for _ in range(unique):
        count, flags = unpack_from("<HB", segments.header(3))
        runs = unpack_from("<H", segments.header(2, next_record=False))[0] if flags & 8 else 0
        extension = unpack_from("<I", segments.header(4, next_record=False))[0] if flags & 4 else 0
        strings.append(segments.characters(count, bool(flags & 1)))
        segments.skip(runs * 4 + extension)
    segments.finish()
    return strings


def read_formula_string(cursor: Cursor, record: Record) -> str:
    segments = Segments(cursor, record)
    count, flags = unpack_from("<HB", segments.header(3))
    value = segments.characters(count, bool(flags & 1))
    segments.finish()
    return value
