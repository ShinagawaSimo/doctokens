"""Conservative, session-local admission and growth estimates, independent of RSS."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass

from .models import ZipEntryInfo


class ParseMemoryLimitError(RuntimeError):
    """A complete session exceeded its configured estimated-memory allowance."""


def estimate_session_bytes(entries: Sequence[ZipEntryInfo]) -> int:
    """Reserve XML expansion, package/cache overhead and small binary parts.

    This includes unused XML parts: admission precedes parsing. It is a heuristic
    reservation, not a bound on Python or native allocations.
    """
    xml_sizes = [e["uncompressedSize"] for e in entries if e["name"].lower().endswith((".xml", ".rels"))]
    binary = sum(e["uncompressedSize"] for e in entries if not e["name"].lower().endswith((".xml", ".rels")))
    # All parts contribute retained data, but XML trees are normally consumed
    # one part at a time. Charging tree expansion for every slide simultaneously
    # would incorrectly treat disposable formatting trees as retained IR.
    return 1024 * 1024 + len(entries) * 1024 + sum(xml_sizes) * 2 + max(xml_sizes, default=0) * 12 + min(binary, 8 * 1024 * 1024)


def object_bytes(value: object) -> int:
    """Visit a completed fragment, following only containers and dataclasses.

    Shared references count once locally. External providers and modules are
    never traversed. XLSX cells use counters instead of recursive object walks.
    """
    pending = [value]
    seen: set[int] = set()
    total = 0
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        total += sys.getsizeof(item)
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            total += sys.getsizeof(vars(item)) if hasattr(item, "__dict__") else 0
            pending.extend(getattr(item, f.name) for f in fields(item))
    return total


class SessionMemoryBudget:
    def __init__(self, limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("memory_limit_bytes must be a positive integer")
        self.limit = limit
        self.reserved = 0
        self.retained = 1024 * 1024

    @property
    def estimated_bytes(self) -> int:
        return max(self.reserved, self.retained)

    def admit(self, entries: Sequence[ZipEntryInfo]) -> None:
        self.reserved = estimate_session_bytes(entries)
        self._check()

    def add_fragment(self, value: object) -> None:
        self.retained += object_bytes(value)
        self._check()

    def finish(self, value: object) -> None:
        self.retained = max(self.retained, 1024 * 1024 + object_bytes(value))
        self._check()

    def add_cells(self, cells: Sequence[Mapping[str, object]]) -> None:
        # Dictionary/indices/scalars and a worst-case Unicode character charge.
        # No recursive walk, global string pool or per-cell seen set.
        self.retained += 128 + sum(
            640 + sum(len(v) * 4 for key in ("ref", "text", "raw", "formula") if isinstance(v := c.get(key), str)) for c in cells
        )
        self._check()

    def _check(self) -> None:
        if self.estimated_bytes > self.limit:
            raise ParseMemoryLimitError(f"estimated session memory {self.estimated_bytes} exceeds allowance {self.limit} bytes")
