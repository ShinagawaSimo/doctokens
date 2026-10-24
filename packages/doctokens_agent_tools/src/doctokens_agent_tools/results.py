"""Byte-bounded LRU storage for immutable text and binary tool results."""

from __future__ import annotations

import json
import time
import uuid
from _thread import RLock
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from doctokens_core.execution import checkpoint, current_control

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
        self.lock = RLock()
        self._transaction_depth = 0
        self.operations: dict[str, set[str]] = {}
        self.entries: OrderedDict[str, StoredResult] = OrderedDict()
        self.keys: dict[str, str] = {}
        self.bytes = 0

    def remove(self, identifier: str) -> None:
        with self.lock:
            entry = self.entries.pop(identifier)
            self.bytes -= entry.size
            for identifiers in self.operations.values():
                identifiers.discard(identifier)
            if entry.key is not None:
                self.keys.pop(entry.key, None)

    def expire(self, active_documents: set[str]) -> None:
        with self.lock:
            now = time.monotonic()
            for entry in list(self.entries.values()):
                if entry.document_id not in active_documents or now - entry.touched >= self.config.result_idle_seconds:
                    self.remove(entry.id)

    def release(self, document_id: str) -> None:
        with self.lock:
            for entry in list(self.entries.values()):
                if entry.document_id == document_id:
                    self.remove(entry.id)

    def get(self, identifier: str) -> StoredResult:
        with self.lock:
            entry = self.entries.get(identifier)
            if entry is None:
                raise ToolError("RESULT_EXPIRED", "result expired or was evicted; repeat the original read")
            entry.touched = time.monotonic()
            self.entries.move_to_end(identifier)
            return entry

    def cached(self, key: str) -> StoredResult | None:
        with self.lock:
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
        with self.lock:
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
            if (control := current_control()) is not None:
                self.operations.setdefault(control.id, set()).add(entry.id)
            self.bytes += size
            if key is not None:
                self.keys[key] = entry.id
            return entry

    def close(self) -> None:
        with self.lock:
            self.entries.clear()
            self.keys.clear()
            self.bytes = 0
            self.operations.clear()

    def finish_operation(self, identifier: str, *, success: bool) -> None:
        with self.lock:
            identifiers = self.operations.pop(identifier, set())
            if not success:
                for result_id in list(identifiers):
                    if result_id in self.entries:
                        self.remove(result_id)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.lock:
            outer = self._transaction_depth == 0
            if outer:
                saved = (self.entries.copy(), self.keys.copy(), self.bytes, {k: set(v) for k, v in self.operations.items()})
            self._transaction_depth += 1
            try:
                checkpoint("presenting result")
                yield
                checkpoint("result ready")
            except BaseException:
                if outer:
                    self.entries, self.keys, self.bytes, self.operations = saved
                raise
            finally:
                self._transaction_depth -= 1
