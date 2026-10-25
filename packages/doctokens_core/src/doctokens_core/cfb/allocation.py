"""MS-CFB header, allocation tables and checked sector chains."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from struct import Struct, unpack_from

from ..execution import checkpoint
from .source import ByteSource, CfbError, CfbUnsupportedError

FREE = 0xFFFFFFFF
END = 0xFFFFFFFE
FAT = 0xFFFFFFFD
DIFAT = 0xFFFFFFFC
MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PAGE = Struct("<128I")


@dataclass(frozen=True, slots=True)
class Header:
    fat_count: int
    directory_start: int
    mini_fat_start: int
    mini_fat_count: int
    difat_start: int
    difat_count: int


class Allocation:
    def __init__(self, source: ByteSource) -> None:
        self.source = source
        raw = source.read_at(0, 512)
        if raw[:8] != MAGIC:
            raise CfbError("Not an OLE Compound File Binary document")
        version, byte_order, shift, mini_shift = unpack_from("<4H", raw, 26)
        if version == 4:
            raise CfbUnsupportedError("CFB version 4 is not supported yet")
        if version != 3 or byte_order != 0xFFFE or shift != 9 or mini_shift != 6:
            raise CfbError("Invalid CFB version, byte order or sector size")
        if source.size % 512 or unpack_from("<I", raw, 56)[0] != 4096:
            raise CfbError("Invalid CFB file length or mini-stream cutoff")
        if unpack_from("<I", raw, 40)[0] != 0:
            raise CfbError("CFB version 3 directory-sector count must be zero")
        values = unpack_from("<8I", raw, 44)
        self.header = Header(values[0], values[1], values[4], values[5], values[6], values[7])
        self.count = source.size // 512 - 1
        if not 0 < self.header.fat_count <= self.count:
            raise CfbError("Invalid CFB FAT sector count")
        if self.header.difat_count > self.count or self.header.mini_fat_count > self.count:
            raise CfbError("Invalid CFB allocation-table size")
        self.owners = array("I", [0]) * self.count
        fat_ids = list(unpack_from("<109I", raw, 76))
        difat_ids: set[int] = set()
        current = self.header.difat_start
        for _ in range(self.header.difat_count):
            self.check_sector(current)
            if current in difat_ids:
                raise CfbError("Cyclic CFB DIFAT chain")
            difat_ids.add(current)
            page = _PAGE.unpack(self.sector(current))
            fat_ids.extend(page[:-1])
            current = page[-1]
        if self.header.difat_count and current != END:
            raise CfbError("CFB DIFAT chain does not end at its declared length")
        candidates = [sector for sector in fat_ids if sector != FREE]
        if len(candidates) != self.header.fat_count or len(set(candidates)) != len(candidates):
            raise CfbError("CFB FAT references disagree with the declared count")
        self.fat = array("I")
        for sector in candidates:
            self.check_sector(sector)
            if sector in difat_ids:
                raise CfbError("CFB FAT overlaps DIFAT")
            self.owners[sector] = 1
            self.fat.extend(_PAGE.unpack(self.sector(sector)))
        if len(self.fat) < self.count:
            raise CfbError("CFB FAT does not cover the file")
        del self.fat[self.count :]
        for sector in candidates:
            if self.fat[sector] != FAT:
                raise CfbError("CFB FAT sector has an invalid allocation marker")
        for sector in difat_ids:
            self.owners[sector] = 2
            if self.fat[sector] != DIFAT:
                raise CfbError("CFB DIFAT sector has an invalid allocation marker")

    def check_sector(self, sector: int) -> None:
        if not 0 <= sector < self.count:
            raise CfbError(f"CFB sector out of range: {sector}")

    def sector(self, sector: int) -> bytes:
        self.check_sector(sector)
        return self.source.read_at((sector + 1) * 512, 512)

    def chain(self, start: int, *, owner: int, limit: int, expected: int | None = None) -> array[int]:
        result = array("I")
        seen = bytearray(self.count)
        current = start
        while current != END:
            checkpoint("indexing compound-file chain")
            self.check_sector(current)
            if seen[current] or self.owners[current] not in (0, owner):
                raise CfbError("Cyclic or overlapping CFB sector chain")
            if len(result) >= limit or (expected is not None and len(result) >= expected):
                raise CfbError("CFB chain exceeds its declared size or configured limit")
            seen[current] = 1
            self.owners[current] = owner
            result.append(current)
            current = self.fat[current]
        if expected is not None and len(result) != expected:
            raise CfbError("CFB chain is shorter than its declared size")
        return result
