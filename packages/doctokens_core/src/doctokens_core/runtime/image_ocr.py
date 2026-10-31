"""Explicit read-session ownership of bounded image OCR and result reuse."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import cast

from ..contracts.models import ParseReport, ParseWarning
from ..contracts.ocr import OcrResultRecord


class ImageOcrReader:
    def __init__(self, provider: object | None, workers: int, timeout: float) -> None:
        self.provider, self.workers, self.timeout = provider, workers, timeout
        self._results: dict[str, OcrResultRecord] = {}

    def clear(self) -> None:
        self._results.clear()

    @staticmethod
    def report(report: ParseReport, results: dict[str, OcrResultRecord], warnings: list[ParseWarning]) -> ParseReport:
        counters = dict(report.metrics.get("counters", {}))
        for key, value in (
            ("ocrResultCount", len(results)),
            ("ocrErrorCount", sum(item.get("status") == "error" for item in results.values())),
        ):
            if key in counters:
                counters[key] = value
        return replace(report, warnings=tuple(warnings), metrics={**report.metrics, "counters": counters})

    def prepare(
        self,
        read_part: Callable[[str], bytes],
        sources: Iterable[tuple[str, str]],
        results: dict[str, OcrResultRecord],
        warnings: list[ParseWarning],
    ) -> None:
        if self.provider is None:
            return
        from ocr_llm_core import OcrResult, run_ocr_batch

        aliases: dict[str, list[str]] = {}
        for asset_id, part in sources:
            aliases.setdefault(part, []).append(asset_id)
        pending: dict[str, bytes] = {}
        pending_bytes = 0

        def store(part: str, value: OcrResultRecord) -> None:
            self._results[part] = value
            if value.get("status") == "error":
                detail = value.get("error_message") or value.get("error_code") or "OCR provider failed"
                warnings.append(ParseWarning("OCR_FAILED", detail, part))

        def flush() -> None:
            nonlocal pending_bytes
            for part, result in run_ocr_batch(pending, self.provider, max_workers=self.workers, timeout=self.timeout).items():
                store(part, cast(OcrResultRecord, result.to_record()))
            pending.clear()
            pending_bytes = 0

        for part in aliases:
            if part in self._results:
                continue
            try:
                data = read_part(part)
            except Exception as exc:
                store(part, cast(OcrResultRecord, OcrResult.error("image_read_error", str(exc)).to_record()))
                continue
            if pending and (len(pending) >= max(1, self.workers * 2) or pending_bytes + len(data) > 64 * 1024 * 1024):
                flush()
            pending[part] = data
            pending_bytes += len(data)
        if pending:
            flush()
        for part, ids in aliases.items():
            for asset_id in ids:
                results[asset_id] = cast(OcrResultRecord, dict(self._results[part]))
