"""A bounded window of matching source units over one explicit XLSX reader."""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterator

from doctokens_core.execution import checkpoint
from doctokens_core.memory import object_bytes
from doctokens_core.text_search import TextSearchOptions, TextSearchResult, TextUnit, search_text
from doctokens_excel import XlsxTextSource

from .documents import Document


class SearchCursor:
    def __init__(self, document: Document, query: str, *, case_sensitive: bool, sheets: list[str] | None) -> None:
        from doctokens_excel import ParseOptions

        assert isinstance(document.options, ParseOptions)
        self.document_id = document.id
        self.query = query
        self.pattern = re.compile(re.escape(query), 0 if case_sensitive else re.IGNORECASE)
        self.source: XlsxTextSource | None = XlsxTextSource(document.snapshot, options=document.options, sheets=sheets)
        self.source.__enter__()
        self.units: Iterator[TextUnit] = iter(self.source)
        self.records: deque[tuple[TextUnit, int]] = deque()
        self.record_bytes = 0
        self.start = 0
        self.done = False
        self.touched = time.monotonic()

    @property
    def size(self) -> int:
        return 1024 + self.record_bytes + (self.source.estimated_memory_bytes if self.source is not None else 0)

    def read(self, options: TextSearchOptions, budget: int) -> TextSearchResult:
        required = options.offset + options.limit + 1
        while not self.done and self.start + len(self.records) < required:
            checkpoint("continuing text search")
            unit = next(self.units, None)
            if unit is None:
                self.done = True
                if self.source is not None:
                    self.source.close()
                    self.source = None
                break
            if self.pattern.search(unit.text) is None:
                continue
            size = object_bytes(unit) + 128
            self.records.append((unit, size))
            self.record_bytes += size
            while self.start < options.offset and self.records and self.size > budget:
                self.record_bytes -= self.records.popleft()[1]
                self.start += 1
        adjusted = TextSearchOptions(
            options.case_sensitive, options.offset - self.start, options.limit, options.context_before, options.context_after
        )
        result = search_text((unit for unit, _size in self.records), self.query, adjusted)
        self.touched = time.monotonic()
        return TextSearchResult(result.matches, result.next_offset + self.start if result.next_offset is not None else None)

    def close(self) -> None:
        if self.source is not None:
            self.source.close()
            self.source = None
        self.records.clear()
        self.record_bytes = 0
