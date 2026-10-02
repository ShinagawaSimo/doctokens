"""Bounded response projection, independent of the transport."""

from __future__ import annotations

import base64
import json
from typing import Any

from ooxml_llm_core.models import ParseResult

from .config import RuntimeConfig
from .documents import Document
from .models import BinaryAttachment, ToolError, ToolResponse
from .results import ResultStore, StoredResult


def identity(document: Document) -> dict[str, Any]:
    return {"document_id": document.id, "revision": document.revision, "path": str(document.original), "format": document.format}


class Presenter:
    def __init__(self, config: RuntimeConfig, results: ResultStore) -> None:
        self.config = config
        self.results = results

    def metadata(self, document: Document, data: dict[str, Any], *, protected: set[str] | None = None) -> ToolResponse:
        value = {**identity(document), **data}
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded) > self.config.reply_chars:
            entry = self.results.put(
                document.id, encoded, {"media_type": "application/json", "syntax_version": "json/1"}, protected=protected
            )
            value = {
                **identity(document),
                "result_id": entry.id,
                "length": len(encoded),
                "media_type": "application/json",
                "content_included": False,
                "next_action": "read_result",
            }
        return ToolResponse(value)

    def parsed(
        self, document: Document, parsed: list[ParseResult], *, extra: dict[str, Any] | None = None, cache_key: str | None = None
    ) -> ToolResponse:
        items = []
        for result in parsed:
            metadata = {
                "density": result.density,
                "selection": dict(result.selection),
                "syntax_version": result.syntax_version,
                "media_type": result.media_type,
                "warning_count": len(result.report.warnings),
            }
            items.append((result.text, metadata))
        required = sum(
            len(text.encode("utf-8")) + len(json.dumps(meta, ensure_ascii=False).encode("utf-8")) + 256 for text, meta in items
        )
        if required > self.config.max_result_bytes:
            if sum(len(text) for text, _ in items) > self.config.reply_chars:
                raise ToolError("RESULT_TOO_LARGE", "selected results exceed storage capacity; request a smaller interval")
            parts = [
                {**meta, "length": len(text), "text": text, "content_included": True, "fragment": False} for text, meta in items
            ]
            return self.metadata(document, {"parts": parts, **(extra or {})})
        entries: list[StoredResult] = []
        for text, meta in items:
            entries.append(
                self.results.put(
                    document.id,
                    text,
                    meta,
                    key=cache_key if len(items) == 1 else None,
                    protected={entry.id for entry in entries},
                )
            )
        return self.entries(document, entries, extra=extra)

    def entries(self, document: Document, entries: list[StoredResult], *, extra: dict[str, Any] | None = None) -> ToolResponse:
        included = sum(len(entry.value) for entry in entries) <= self.config.reply_chars
        parts = []
        for entry in entries:
            part = {
                **entry.metadata,
                "result_id": entry.id,
                "length": len(entry.value),
                "content_included": included,
                "fragment": False,
            }
            if included:
                part["text"] = entry.value
            parts.append(part)
        data = {"parts": parts, **(extra or {})}
        if not included:
            data["next_action"] = "read_result"
        return self.metadata(document, data, protected={entry.id for entry in entries})

    def binary(self, document: Document, value: bytes, media_type: str) -> ToolResponse:
        metadata = {"media_type": media_type, "unit": "bytes"}
        entry = self.results.put(document.id, value, metadata)
        data = {**identity(document), **metadata, "result_id": entry.id, "length": len(value)}
        if len(value) <= self.config.max_inline_binary_bytes:
            return ToolResponse(data, attachments=(BinaryAttachment(value, media_type),))
        data["next_action"] = "read_result"
        return ToolResponse(data)

    def fragment(self, identifier: str, offset: int, length: int | None) -> ToolResponse:
        entry = self.results.get(identifier)
        amount = self.config.result_chunk_chars if length is None else length
        if amount > self.config.max_chunk_size:
            raise ToolError("INVALID_ARGUMENT", f"length cannot exceed {self.config.max_chunk_size}")
        if offset > len(entry.value):
            raise ToolError("INVALID_ARGUMENT", "offset exceeds the result length")
        amount = min(amount, self.config.reply_chars)
        if isinstance(entry.value, bytes):
            amount = min(amount, max(1, self.config.reply_chars * 3 // 4))
        value = entry.value[offset : offset + amount]
        next_offset = offset + len(value)
        data = {
            **entry.metadata,
            "result_id": entry.id,
            "document_id": entry.document_id,
            "fragment": True,
            "offset": offset,
            "length": len(value),
            "total_length": len(entry.value),
            "next_offset": next_offset if next_offset < len(entry.value) else None,
        }
        if isinstance(value, bytes):
            data.update(unit="bytes", encoding="base64", data=base64.b64encode(value).decode("ascii"))
        else:
            data.update(unit="characters", text=value)
        return ToolResponse(data)
