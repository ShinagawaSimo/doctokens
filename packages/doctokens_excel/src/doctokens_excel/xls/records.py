"""Checked BIFF8 record boundaries over a bounded logical stream buffer."""

from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

from doctokens_core.containers.cfb.stream import CfbStream
from doctokens_core.runtime.execution import checkpoint

from .models import XlsError, XlsLimits


@dataclass(frozen=True, slots=True)
class Record:
    kind: int
    offset: int
    size: int


@dataclass(slots=True)
class Budget:
    limits: XlsLimits
    records: int = 0
    characters: int = 0
    cells: int = 0

    def add_string(self, count: int) -> None:
        self.characters += count
        if count > self.limits.max_string_characters or self.characters > self.limits.max_total_string_characters:
            raise XlsError("XLS string content exceeds its configured limit")


class Cursor:
    def __init__(self, stream: CfbStream, budget: Budget, offset: int = 0) -> None:
        self.stream = stream
        self.budget = budget
        self.position = offset
        self._start = 0
        self._buffer = b""

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset > self.stream.size or size > self.stream.size - offset:
            raise XlsError(f"Truncated BIFF data at Workbook offset {offset}")
        relative = offset - self._start
        if relative < 0 or relative + size > len(self._buffer):
            self._start = offset
            self._buffer = self.stream.read_at(offset, min(64 * 1024, self.stream.size - offset))
            relative = 0
        return self._buffer[relative : relative + size]

    def peek(self) -> Record:
        kind, size = unpack_from("<HH", self.read_at(self.position, 4))
        if size > 8224 or size > self.stream.size - self.position - 4:
            raise XlsError(f"Invalid BIFF record length at Workbook offset {self.position}")
        return Record(kind, self.position, size)

    def next(self) -> Record:
        checkpoint("reading XLS records")
        self.budget.records += 1
        if self.budget.records > self.budget.limits.max_records:
            raise XlsError("XLS exceeds max_records")
        record = self.peek()
        self.position += 4 + record.size
        return record

    def payload(self, record: Record, minimum: int = 0) -> bytes:
        if record.size < minimum:
            raise XlsError(f"Short BIFF record 0x{record.kind:04x} at {record.offset}")
        return self.read_at(record.offset + 4, record.size)


def read_bof(cursor: Cursor, expected: int) -> None:
    record = cursor.next()
    if record.kind != 0x0809:
        raise XlsError(f"Expected BIFF8 BOF at Workbook offset {record.offset}")
    version, kind = unpack_from("<HH", cursor.payload(record, 16))
    if version != 0x0600:
        raise XlsError(f"Only BIFF8 is supported (BOF version 0x{version:04x})")
    if kind != expected:
        raise XlsError(f"Unexpected BIFF substream type 0x{kind:04x}")
