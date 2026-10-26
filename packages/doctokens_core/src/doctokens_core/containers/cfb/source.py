"""Explicit ownership and exact physical reads for compound files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ...runtime.execution import checkpoint


class CfbError(ValueError):
    """The compound file is invalid or exceeds a configured limit."""


class CfbUnsupportedError(CfbError):
    """The input requires a compound-file feature that is not implemented."""


@dataclass(frozen=True, slots=True)
class CfbLimits:
    max_file_bytes: int = 256 * 1024 * 1024
    max_stream_bytes: int = 128 * 1024 * 1024
    max_directory_entries: int = 32_768

    def __post_init__(self) -> None:
        for name in ("max_file_bytes", "max_stream_bytes", "max_directory_entries"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


class ByteSource:
    """Own a path's file handle or retain immutable caller-provided bytes."""

    def __init__(self, source: str | Path | bytes, limits: CfbLimits) -> None:
        self._file: BinaryIO | None = None
        self._data: bytes | None = None
        self.closed = False
        try:
            if isinstance(source, bytes):
                self.size = len(source)
                self._data = source
            else:
                self._file = Path(source).open("rb")  # noqa: SIM115 -- Owned until ByteSource.close().
                self._file.seek(0, 2)
                self.size = self._file.tell()
            if self.size > limits.max_file_bytes:
                raise CfbError("Compound file exceeds max_file_bytes")
        except BaseException:
            self.close()
            raise

    def read_at(self, offset: int, size: int) -> bytes:
        if self.closed:
            raise RuntimeError("Compound file is closed")
        checkpoint("reading compound file")
        if offset < 0 or size < 0 or offset > self.size or size > self.size - offset:
            raise CfbError(f"Physical read outside compound file at {offset}, length {size}")
        if self._data is not None:
            result = self._data[offset : offset + size]
        elif self._file is not None:
            self._file.seek(offset)
            result = self._file.read(size)
        else:
            raise RuntimeError("Compound file has no source")
        if len(result) != size:
            raise CfbError(f"Truncated compound file at {offset}")
        checkpoint("reading compound file")
        return result

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self._data = None
        self.closed = True
