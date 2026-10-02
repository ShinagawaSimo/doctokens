"""Byte-bounded LRU storage for immutable text and binary tool results."""

from __future__ import annotations

import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .config import RuntimeConfig
from .models import ToolError


@dataclass
class StoredResult:
    id: str
    document_id: str
    value: str | bytes
    metadata: dict[str, Any]
    size: int
    touched: float
    key: str | None = None


class ResultStore:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.entries: OrderedDict[str, StoredResult] = OrderedDict()
        self.keys: dict[str, str] = {}
        self.bytes = 0

    def remove(self, identifier: str) -> None:
        entry = self.entries.pop(identifier)
        self.bytes -= entry.size
        if entry.key is not None:
            self.keys.pop(entry.key, None)

    def expire(self, active_documents: set[str]) -> None:
        now = time.monotonic()
        for entry in list(self.entries.values()):
            if entry.document_id not in active_documents or now - entry.touched >= self.config.result_idle_seconds:
                self.remove(entry.id)

    def release(self, document_id: str) -> None:
        for entry in list(self.entries.values()):
            if entry.document_id == document_id:
                self.remove(entry.id)

    def get(self, identifier: str) -> StoredResult:
        entry = self.entries.get(identifier)
        if entry is None:
            raise ToolError("RESULT_EXPIRED", "result expired or was evicted; repeat the original read")
        entry.touched = time.monotonic()
        self.entries.move_to_end(identifier)
        return entry

    def cached(self, key: str) -> StoredResult | None:
        identifier = self.keys.get(key)
        return self.get(identifier) if identifier is not None else None

    def put(
        self,
        document_id: str,
        value: str | bytes,
        metadata: dict[str, Any],
        *,
        key: str | None = None,
        protected: set[str] | None = None,
    ) -> StoredResult:
        size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
        size += len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) + 256
        pinned = protected or set()
        reserved = sum(self.entries[identifier].size for identifier in pinned)
        if size + reserved > self.config.max_result_bytes:
            raise ToolError(
                "RESULT_TOO_LARGE", "complete result exceeds storage capacity; reduce the selection or raise the host limit"
            )
        if key is not None and key in self.keys:
            self.remove(self.keys[key])
        while self.entries and self.bytes + size > self.config.max_result_bytes:
            victim = next(identifier for identifier in self.entries if identifier not in pinned)
            self.remove(victim)
        entry = StoredResult(uuid.uuid4().hex, document_id, value, metadata, size, time.monotonic(), key)
        self.entries[entry.id] = entry
        self.bytes += size
        if key is not None:
            self.keys[key] = entry.id
        return entry

    def close(self) -> None:
        self.entries.clear()
        self.keys.clear()
        self.bytes = 0
