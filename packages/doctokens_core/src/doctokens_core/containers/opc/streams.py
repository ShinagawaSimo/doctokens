"""Cooperative cancellation around OPC ZIP entry reads."""

from __future__ import annotations

from io import BufferedReader
from zipfile import ZipExtFile

from ...runtime.execution import checkpoint


class CheckedReader(BufferedReader):
    def __init__(self, source: ZipExtFile) -> None:
        super().__init__(source)

    def read(self, size: int | None = -1) -> bytes:
        checkpoint("reading package bytes")
        value = super().read(size)
        checkpoint("reading package bytes")
        return value
