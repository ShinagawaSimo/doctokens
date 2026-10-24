"""Sparse, slotted cell mapping used by the retained XLSX cell IR."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from enum import Enum


class _Missing(Enum):
    VALUE = 0


_MISSING = _Missing.VALUE
_CORE_KEYS = ("ref", "row", "col", "text", "raw", "type", "style")
_SLOT_KEYS = frozenset(_CORE_KEYS)


class CompactCell(MutableMapping[str, object]):
    """Internal mutable mapping with common fields in slots and sparse extras.

    Iteration uses a fixed core-field order, followed by extras. Construction
    leaves the input mapping intact; shared values retain their identity.
    """

    __slots__ = ("_extra", "col", "raw", "ref", "row", "style", "text", "type")

    ref: object
    row: object
    col: object
    text: object
    raw: object
    type: object
    style: object
    _extra: dict[str, object] | None

    def __init__(self, values: Mapping[str, object]) -> None:
        self.ref = values.get("ref", _MISSING)
        self.row = values.get("row", _MISSING)
        self.col = values.get("col", _MISSING)
        self.text = values.get("text", _MISSING)
        self.raw = values.get("raw", _MISSING)
        self.type = values.get("type", _MISSING)
        self.style = values.get("style", _MISSING)
        self._extra = {key: value for key, value in values.items() if key not in _SLOT_KEYS} or None

    def __getitem__(self, key: str) -> object:
        if key in _SLOT_KEYS:
            value = getattr(self, key)
            if value is _MISSING:
                raise KeyError(key)
            return value
        if self._extra is not None:
            return self._extra[key]
        raise KeyError(key)

    def get(self, key: str, default: object = None) -> object:
        if key in _SLOT_KEYS:
            value = getattr(self, key)
            return default if value is _MISSING else value
        if self._extra is not None:
            return self._extra.get(key, default)
        return default

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        if key in _SLOT_KEYS:
            return getattr(self, key) is not _MISSING
        return self._extra is not None and key in self._extra

    def __setitem__(self, key: str, value: object) -> None:
        if key in _SLOT_KEYS:
            setattr(self, key, value)
            return
        if self._extra is None:
            self._extra = {}
        self._extra[key] = value

    def __delitem__(self, key: str) -> None:
        if key in _SLOT_KEYS:
            if getattr(self, key) is _MISSING:
                raise KeyError(key)
            setattr(self, key, _MISSING)
            return
        if self._extra is None:
            raise KeyError(key)
        del self._extra[key]
        if not self._extra:
            self._extra = None

    def __iter__(self) -> Iterator[str]:
        for key in _CORE_KEYS:
            if getattr(self, key) is not _MISSING:
                yield key
        if self._extra is not None:
            yield from self._extra

    def __len__(self) -> int:
        return sum(getattr(self, key) is not _MISSING for key in _CORE_KEYS) + (
            len(self._extra) if self._extra is not None else 0
        )
