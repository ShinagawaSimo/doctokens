"""Runtime-owned XLSX search continuation; public offsets remain ordinary integers."""

from __future__ import annotations

import time
from _thread import RLock
from collections import OrderedDict

from doctokens_core.text_search import TextSearchOptions, TextSearchResult

from .config import RuntimeConfig
from .documents import Document
from .search_cursor import SearchCursor

Key = tuple[str, str, bool, tuple[str, ...] | None]


class SearchCache:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.lock = RLock()
        self.entries: OrderedDict[Key, SearchCursor] = OrderedDict()
        self.bytes = 0

    def _remove(self, key: Key) -> None:
        cursor = self.entries.pop(key)
        self.bytes -= cursor.size
        cursor.close()

    def release(self, identifier: str) -> None:
        with self.lock:
            for key in list(self.entries):
                if key[0] == identifier:
                    self._remove(key)

    def expire(self, documents: set[str]) -> None:
        with self.lock:
            for key, cursor in list(self.entries.items()):
                if key[0] not in documents or time.monotonic() - cursor.touched >= self.config.search_idle_seconds:
                    self._remove(key)

    def close(self) -> None:
        with self.lock:
            for key in list(self.entries):
                self._remove(key)

    def search(self, document: Document, query: str, options: TextSearchOptions, sheets: list[str] | None) -> TextSearchResult:
        # Validate identically to one-shot search, before opening any reader.
        from doctokens_core.text_search import TextSearchCollector

        TextSearchCollector(query, options)
        key = (document.id, query, options.case_sensitive, tuple(sheets) if sheets is not None else None)
        with self.lock:
            cursor = self.entries.pop(key, None)
            if cursor is not None:
                self.bytes -= cursor.size
                if options.offset < cursor.start:
                    cursor.close()
                    cursor = None
        cursor = cursor or SearchCursor(document, query, case_sensitive=options.case_sensitive, sheets=sheets)
        try:
            result = cursor.read(options, self.config.max_search_bytes)
        except BaseException:
            cursor.close()
            raise
        with self.lock:
            size = cursor.size
            if size > self.config.max_search_bytes:
                cursor.close()
                return result
            while self.entries and (
                self.bytes + size > self.config.max_search_bytes or len(self.entries) >= self.config.max_search_states
            ):
                self._remove(next(iter(self.entries)))
            self.entries[key] = cursor
            self.bytes += size
        return result
