"""Root-level stream discovery without a recursive object/metadata tree."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from
from types import TracebackType

from ..execution import checkpoint
from .allocation import END, FREE, Allocation
from .source import ByteSource, CfbError, CfbLimits
from .stream import CfbStream


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    sid: int
    name: str
    kind: int
    left: int
    right: int
    child: int
    start: int
    size: int


class CfbReader:
    """An entered reader owns one source; its streams share that lifetime."""

    def __init__(self, source: str | Path | bytes, *, limits: CfbLimits | None = None) -> None:
        self._input = source
        self.limits = limits or CfbLimits()
        self._source: ByteSource | None = None
        self._allocation: Allocation | None = None
        self._entered = False
        self._directory: CfbStream | None = None
        self._mini_root: CfbStream | None = None
        self._mini_fat: array[int] | None = None
        self._pages: dict[int, bytes] = {}
        self._entries: dict[str, DirectoryEntry] = {}

    def __enter__(self) -> CfbReader:
        if self._entered:
            raise RuntimeError("CfbReader cannot be entered twice")
        self._entered = True
        try:
            self._source = ByteSource(self._input, self.limits)
            allocation = Allocation(self._source)
            self._allocation = allocation
            maximum = (self.limits.max_directory_entries + 3) // 4
            chain = allocation.chain(allocation.header.directory_start, owner=3, limit=maximum)
            if not chain:
                raise CfbError("CFB directory is empty")
            self._directory = CfbStream(self._source, chain, len(chain) * 512)
            self._root = self._entry(0)
            if self._root.kind != 5:
                raise CfbError("CFB directory entry zero is not the root")
            self._index_root()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        if self._source is not None:
            self._source.close()
            self._source = None
        self._directory = None
        self._allocation = None
        self._input = b""
        self._mini_root = None
        self._mini_fat = None
        self._pages.clear()
        self._entries.clear()

    def _entry(self, sid: int) -> DirectoryEntry:
        if self._directory is None:
            raise RuntimeError("CfbReader is not open")
        if not 0 <= sid < min(self._directory.size // 128, self.limits.max_directory_entries):
            raise CfbError("CFB directory entry is out of range")
        page, slot = divmod(sid, 4)
        if page not in self._pages:
            if len(self._pages) >= 8:
                self._pages.pop(next(iter(self._pages)))
            self._pages[page] = self._directory.read_at(page * 512, 512)
        raw = self._pages[page][slot * 128 : (slot + 1) * 128]
        length, kind = unpack_from("<HB", raw, 64)
        if kind not in (1, 2, 5) or not 2 <= length <= 64 or length % 2 or raw[length - 2 : length] != b"\0\0":
            raise CfbError("Invalid CFB directory name or entry type")
        try:
            name = raw[: length - 2].decode("utf-16le")
        except UnicodeDecodeError as exc:
            raise CfbError("Invalid UTF-16 CFB directory name") from exc
        left, right, child = unpack_from("<3I", raw, 68)
        start, size = unpack_from("<2I", raw, 116)
        # MS-CFB recommends ignoring uninitialized size high bits in v3.
        return DirectoryEntry(sid, name, kind, left, right, child, start, size)

    def _index_root(self) -> None:
        stack = [self._root.child]
        seen = {0}
        while stack:
            checkpoint("reading CFB root directory")
            sid = stack.pop()
            if sid == FREE:
                continue
            if sid in seen:
                raise CfbError("Cyclic or multiply referenced CFB directory entry")
            seen.add(sid)
            entry = self._entry(sid)
            if entry.kind == 5:
                raise CfbError("CFB contains a second root entry")
            key = entry.name.upper()
            if key in self._entries:
                raise CfbError("Duplicate name in CFB root directory")
            self._entries[key] = entry
            stack.extend((entry.left, entry.right))

    def has_root_stream(self, name: str) -> bool:
        if self._source is None:
            raise RuntimeError("CfbReader is not open")
        entry = self._entries.get(name.upper())
        return entry is not None and entry.kind == 2

    def open_root_stream(self, name: str) -> CfbStream:
        allocation = self._allocation
        if self._source is None or allocation is None:
            raise RuntimeError("CfbReader is not open")
        entry = self._entries.get(name.upper())
        if entry is None or entry.kind != 2:
            raise CfbError(f"Missing CFB root stream: {name}")
        if entry.size > self.limits.max_stream_bytes:
            raise CfbError("CFB stream exceeds max_stream_bytes")
        if entry.size >= 4096 or entry.size == 0:
            count = (entry.size + 511) // 512
            chain = allocation.chain(entry.start, owner=entry.sid + 8, limit=count, expected=count)
            return CfbStream(self._source, chain, entry.size)
        self._load_mini()
        if self._mini_fat is None or self._mini_root is None:
            raise CfbError("Missing CFB mini stream")
        chain = array("I")
        current = entry.start
        expected = (entry.size + 63) // 64
        seen: set[int] = set()
        while current != END:
            if not 0 <= current < min(len(self._mini_fat), self._mini_root.size // 64) or current in seen:
                raise CfbError("Invalid or cyclic CFB mini-sector chain")
            if len(chain) >= expected:
                raise CfbError("CFB mini-sector chain exceeds the declared size")
            seen.add(current)
            chain.append(current)
            current = self._mini_fat[current]
        if len(chain) != expected:
            raise CfbError("CFB mini-sector chain is shorter than the declared size")
        return CfbStream(self._mini_root, chain, entry.size, mini=True)

    def _load_mini(self) -> None:
        if self._mini_fat is not None:
            return
        allocation = self._allocation
        if self._source is None or allocation is None:
            raise RuntimeError("CfbReader is not open")
        header = allocation.header
        count = (self._root.size + 511) // 512
        if self._root.size > self.limits.max_stream_bytes:
            raise CfbError("CFB root mini stream exceeds max_stream_bytes")
        root_chain = allocation.chain(self._root.start, owner=4, limit=count, expected=count)
        self._mini_root = CfbStream(self._source, root_chain, self._root.size)
        fat_chain = allocation.chain(header.mini_fat_start, owner=5, limit=header.mini_fat_count, expected=header.mini_fat_count)
        self._mini_fat = array("I")
        for sector in fat_chain:
            raw = allocation.sector(sector)
            self._mini_fat.extend(unpack_from("<128I", raw))
