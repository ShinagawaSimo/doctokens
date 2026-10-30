"""Bounded EMF text records, without rendering, OCR, glyph guessing or geometric joining."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import IO, TypedDict

from ..runtime.execution import checkpoint

MAX_RECORDS = 100_000
MAX_CHARACTERS = 16_000
_CODEPAGES = {
    128: "cp932",
    129: "cp949",
    130: "johab",
    134: "gbk",
    136: "big5",
    161: "cp1253",
    162: "cp1254",
    163: "cp1258",
    177: "cp1255",
    178: "cp1256",
    186: "cp1257",
    204: "cp1251",
    222: "cp874",
    238: "cp1250",
}


class EmfSegment(TypedDict, total=False):
    text: str
    reason: str


@dataclass(slots=True)
class EmfText:
    segments: list[EmfSegment] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    characters: int = 0
    recognized: bool = False

    def limit(self, reason: str) -> None:
        if reason not in self.limitations:
            self.limitations.append(reason)

    def add(self, data: bytes, *, unicode: bool, options: int, codec: str | None) -> bool:
        if options & 0x10:
            return self.gap("glyph-indices")
        if not unicode and codec is None:
            return self.gap("unresolved-codepage")
        try:
            value = data.decode("utf-16-le" if unicode else codec or "", errors="strict")
        except UnicodeError:
            return self.gap("invalid-text-encoding")
        if any((ord(c) < 32 and c not in "\t\r\n") or ord(c) in {0xFFFE, 0xFFFF} for c in value):
            value = "".join(c if (ord(c) >= 32 or c in "\t\r\n") and ord(c) not in {0xFFFE, 0xFFFF} else "\ufffd" for c in value)
            self.limit("xml-character-unrepresentable")
        remaining = MAX_CHARACTERS - self.characters
        if len(value) > remaining:
            if remaining:
                self.segments.append({"text": value[:remaining]})
                self.characters += remaining
            self.limit("character-limit")
            return False
        if value:
            self.segments.append({"text": value})
            self.characters += len(value)
        return True

    def gap(self, reason: str) -> bool:
        self.limit(reason)
        if self.characters + 64 > MAX_CHARACTERS:
            self.limit("character-limit")
            return False
        self.segments.append({"reason": reason})
        self.characters += 64
        return True


def read_emf_text(stream: IO[bytes], size: int) -> EmfText:
    result = EmfText()
    header = stream.read(8)
    if len(header) != 8:
        result.limit("invalid-emf-header")
        return result
    kind, length = struct.unpack("<II", header)
    if kind != 1 or not 88 <= length <= size or length % 4:
        result.limit("unsupported-image-format")
        return result
    record = header + stream.read(length - 8)
    if len(record) != length or record[40:44] != b" EMF":
        result.limit("invalid-emf-header")
        return result
    result.recognized = True
    declared = struct.unpack_from("<I", record, 48)[0]
    if declared != size:
        result.limit("inconsistent-emf-size")
    position = length
    fonts: dict[int, int] = {}
    charset: int | None = None
    states: list[int | None] = []
    eof = False
    for ordinal in range(1, MAX_RECORDS):
        if ordinal % 128 == 1:
            checkpoint("reading saved EMF text")
        header = stream.read(8)
        if not header:
            break
        if len(header) != 8:
            result.limit("truncated-record")
            break
        kind, length = struct.unpack("<II", header)
        if length < 8 or length % 4 or length > size - position:
            result.limit("invalid-record-size")
            break
        record = header + stream.read(length - 8)
        position += length
        if len(record) != length:
            result.limit("truncated-record")
            break
        if kind == 14:
            eof = True
            break
        if kind == 82 and length >= 104:
            fonts[struct.unpack_from("<I", record, 8)[0]] = record[35]
        elif kind == 37 and length >= 12:
            handle = struct.unpack_from("<I", record, 8)[0]
            if handle in fonts:
                charset = fonts[handle]
            elif handle & 0x80000000 and (handle & 0x7FFFFFFF) in {10, 11, 12, 13, 14, 16, 17}:
                charset = None
        elif kind == 40 and length >= 12:
            fonts.pop(struct.unpack_from("<I", record, 8)[0], None)
        elif kind == 33:
            states.append(charset)
        elif kind == 34 and length >= 12:
            relative = struct.unpack_from("<i", record, 8)[0]
            index = len(states) + relative if relative < 0 else relative - 1
            if 0 <= index < len(states):
                charset = states[index]
                del states[index:]
            else:
                charset = None
                result.limit("invalid-dc-state")
        elif kind in {83, 84}:
            if not _text_record(record, 36, kind == 84, charset, result):
                return result
        elif kind in {96, 97}:
            if length < 40:
                result.limit("invalid-text-record")
                continue
            count = struct.unpack_from("<I", record, 36)[0]
            if count > (length - 40) // 40:
                result.limit("invalid-text-record")
                continue
            for index in range(count):
                if not _text_record(record, 40 + index * 40, kind == 97, charset, result):
                    return result
        elif kind == 108:
            if not result.gap("unsupported-small-text-record"):
                return result
        elif kind == 70 and length >= 16 and record[12:16] == b"EMF+":
            result.limit("emf-plus-content")
    else:
        result.limit("record-limit")
    if not eof:
        result.limit("missing-eof")
    return result


def _text_record(record: bytes, offset: int, unicode: bool, charset: int | None, result: EmfText) -> bool:
    if offset + 40 > len(record):
        return result.gap("invalid-text-record")
    count, string_offset, options = struct.unpack_from("<III", record, offset + 8)
    width = 2 if unicode else 1
    end = string_offset + count * width
    if count and (string_offset < offset + 40 or end > len(record)):
        return result.gap("invalid-text-record")
    return result.add(record[string_offset:end], unicode=unicode, options=options, codec=_CODEPAGES.get(charset or -1))
