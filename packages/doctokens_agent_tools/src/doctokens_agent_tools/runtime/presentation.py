"""Bounded first-content responses with only actionable reading metadata."""

from __future__ import annotations

import base64
import json
from typing import Any

from doctokens_core.contracts.models import ParseResult

from ..contracts.config import RuntimeConfig
from ..contracts.models import BinaryAttachment, ToolError, ToolResponse
from ..state.documents import Document
from ..state.results import ResultStore, StoredResult


def identity(document: Document) -> dict[str, Any]:
    return {"document_id": document.id}


def reading_selection(selection: dict[str, Any]) -> dict[str, Any]:
    if "windows" not in selection:
        return dict(selection)
    windows = []
    for source in selection["windows"]:
        window = {key: source[key] for key in ("returned_range", "cell_count") if key in source}
        for key in ("next_row", "merged_ranges", "truncated"):
            if source.get(key):
                window[key] = source[key]
        windows.append(window)
    return {"sheet": selection["sheet"], "windows": windows}


class Presenter:
    def __init__(self, config: RuntimeConfig, results: ResultStore) -> None:
        self.config = config
        self.results = results

    def metadata(self, document: Document, data: dict[str, Any], *, protected: set[str] | None = None) -> ToolResponse:
        with self.results.transaction():
            value = {**identity(document), **data}
            encoded = json.dumps(value, ensure_ascii=False)
            if len(encoded) <= self.config.reply_chars:
                return ToolResponse(value)
            entry = self.results.put(document.id, encoded, {"media_type": "application/json"}, protected=protected)
            first = self.fragment(entry.id, 0, min(self.config.reply_chars, self.config.max_chunk_size))
            first.data.update(document_id=document.id, result_id=entry.id, media_type="application/json")
            return first

    def parsed(
        self, document: Document, parsed: list[ParseResult], *, extra: dict[str, Any] | None = None, cache_key: str | None = None
    ) -> ToolResponse:
        items = [
            (
                result.text,
                {
                    "selection": reading_selection(dict(result.selection)),
                    "media_type": result.media_type,
                    "warnings": sorted({warning.code for warning in result.report.warnings}),
                },
            )
            for result in parsed
        ]
        return self.text_parts(document, items, extra=extra, cache_key=cache_key)

    def text_parts(
        self,
        document: Document,
        items: list[tuple[str, dict[str, Any]]],
        *,
        extra: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> ToolResponse:
        with self.results.transaction():
            if cache_key is None and sum(len(text) for text, _ in items) <= min(
                self.config.reply_chars, self.config.max_chunk_size
            ):
                parts = [{"selection": meta["selection"], "media_type": meta["media_type"], "text": text} for text, meta in items]
                data = {"parts": parts, **(extra or {})}
                warnings = sorted({code for _, meta in items for code in meta.get("warnings", [])})
                if warnings:
                    data["warnings"] = warnings
                # Bound metadata independently, without quoting the document text
                # into a second JSON result merely because XML contains quotes.
                if self._metadata_size(data) <= self.config.reply_chars:
                    return ToolResponse({**identity(document), **data})
            required = sum(
                len(text.encode("utf-8")) + len(json.dumps(meta, ensure_ascii=False).encode("utf-8")) + 256
                for text, meta in items
            )
            if required > self.config.max_result_bytes:
                raise ToolError("RESULT_TOO_LARGE", "selected results exceed storage capacity; request a smaller interval")
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

    @staticmethod
    def _metadata_size(data: dict[str, Any]) -> int:
        meta = {**data, "parts": [{key: value for key, value in part.items() if key != "text"} for part in data["parts"]]}
        return len(json.dumps(meta, ensure_ascii=False))

    def entries(self, document: Document, entries: list[StoredResult], *, extra: dict[str, Any] | None = None) -> ToolResponse:
        with self.results.transaction():
            restored: list[StoredResult] = []
            for entry in entries:
                if entry.id not in self.results.entries:
                    entry = self.results.put(
                        document.id, entry.value, entry.metadata, key=entry.key, protected={item.id for item in restored}
                    )
                restored.append(entry)
            entries = restored
            parts = [
                {
                    "selection": entry.metadata["selection"],
                    "media_type": entry.metadata["media_type"],
                    "result_id": entry.id,
                    "next_offset": 0,
                }
                for entry in entries
            ]
            data = {"parts": parts, **(extra or {})}
            warnings = sorted({code for entry in entries for code in entry.metadata.get("warnings", [])})
            if warnings:
                data["warnings"] = warnings
            if self._metadata_size(data) > self.config.reply_chars:
                return self.metadata(document, data, protected={entry.id for entry in entries})
            remaining = min(self.config.reply_chars, self.config.max_chunk_size)
            for entry, part in zip(entries, parts, strict=True):
                assert isinstance(entry.value, str)
                value = entry.value[:remaining]
                if value:
                    part["text"] = value
                remaining -= len(value)
                if len(value) < len(entry.value):
                    part["next_offset"] = len(value)
                else:
                    part.pop("result_id")
                    part.pop("next_offset")
            return ToolResponse({**identity(document), **data})

    def binary(self, document: Document, value: bytes, media_type: str) -> ToolResponse:
        with self.results.transaction():
            metadata = {"media_type": media_type, "unit": "bytes"}
            entry = self.results.put(document.id, value, metadata)
            data = {
                **identity(document),
                **metadata,
                "result_id": entry.id,
                "length": len(value),
                "resource_uri": f"doctokens://result/{entry.id}",
            }
            if len(value) <= self.config.max_inline_binary_bytes:
                return ToolResponse(data, attachments=(BinaryAttachment(value, media_type),))
            return ToolResponse(data)

    def fragment(self, identifier: str, offset: int, length: int | None) -> ToolResponse:
        with self.results.transaction():
            amount = min(self.config.result_chunk_chars, self.config.max_chunk_size) if length is None else length
            if amount > self.config.max_chunk_size:
                raise ToolError("INVALID_ARGUMENT", f"length cannot exceed {self.config.max_chunk_size}")
            entry = self.results.get(identifier)
            if offset > len(entry.value):
                raise ToolError("INVALID_ARGUMENT", "offset exceeds the result length")
            amount = min(amount, self.config.reply_chars)
            if isinstance(entry.value, bytes):
                amount = min(amount, self.config.reply_chars // 4 * 3)
            value = entry.value[offset : offset + amount]
            end = offset + len(value)
            data: dict[str, Any] = {"next_offset": end if end < len(entry.value) else None}
            if isinstance(value, bytes):
                data.update(unit="bytes", encoding="base64", data=base64.b64encode(value).decode("ascii"))
            else:
                data["text"] = value
            return ToolResponse(data)
