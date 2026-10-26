"""Conservative, session-local admission and growth estimates, independent of RSS."""

from __future__ import annotations

import sys
from dataclasses import fields, is_dataclass


class ParseMemoryLimitError(RuntimeError):
    """A complete session exceeded its configured estimated-memory allowance."""


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
