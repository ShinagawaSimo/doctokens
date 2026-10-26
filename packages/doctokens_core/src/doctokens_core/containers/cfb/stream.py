"""Logical stream views; payload is never assembled at stream-open time."""

from __future__ import annotations

from array import array

from .source import ByteSource, CfbError


class CfbStream:
    def __init__(self, source: ByteSource | CfbStream, chain: array[int], size: int, *, mini: bool = False) -> None:
        self._source = source
        self._chain = chain
        self.size = size
        self._unit = 64 if mini else 512
        self._base = 0 if mini else 512

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset > self.size or size > self.size - offset:
            raise CfbError(f"Logical read outside CFB stream at {offset}, length {size}")
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            index, within = divmod(offset, self._unit)
            first = self._chain[index]
            amount = min(remaining, self._unit - within)
            next_index = index + 1
            while amount < remaining and next_index < len(self._chain):
                if self._chain[next_index] != self._chain[next_index - 1] + 1:
                    break
                amount += min(remaining - amount, self._unit)
                next_index += 1
            chunks.append(self._source.read_at(self._base + first * self._unit + within, amount))
            offset += amount
            remaining -= amount
        # A zero-length read still checks the underlying owner's lifetime.
        if not chunks:
            self._source.read_at(0, 0)
            return b""
        return chunks[0] if len(chunks) == 1 else b"".join(chunks)
