"""Provider-agnostic OCR batching used by Office parsers."""

from __future__ import annotations

import hashlib
import inspect
import math
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from ._provider import OcrResult, OcrStatus


def run_ocr_batch(
    images: Mapping[str, bytes],
    provider: object,
    *,
    max_workers: int = 4,
    timeout: float | None = 120.0,
) -> dict[str, OcrResult]:
    """OCR unique image bytes and map outcomes back to asset IDs."""
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError("max_workers must be greater than zero")
    if timeout is not None and (
        isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0
    ):
        raise ValueError("timeout must be greater than zero")

    by_hash: dict[str, bytes] = {}
    image_hashes: dict[str, str] = {}
    for asset_id, data in images.items():
        if not isinstance(asset_id, str) or not asset_id:
            raise TypeError("images must contain non-empty string keys")
        if not isinstance(data, bytes):
            raise TypeError("images must contain bytes values")
        image_hash = hashlib.sha256(data).hexdigest()
        image_hashes[asset_id] = image_hash
        by_hash.setdefault(image_hash, data)
    if not by_hash:
        return {}

    declared_limit = getattr(provider, "max_concurrency", 1)
    try:
        concurrency_limit = max(1, int(declared_limit))
    except (OverflowError, TypeError, ValueError):
        concurrency_limit = 1
    workers = min(max_workers, concurrency_limit, len(by_hash))

    results_by_hash: dict[str, OcrResult] = {}
    # Timeout enforcement is delegated to providers that can actually cancel
    # their work. Returning while native OCR threads are still mutating a
    # shared provider creates races and does not stop the underlying process.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[OcrResult], str] = {
            executor.submit(_invoke_provider, provider, data, timeout): image_hash for image_hash, data in by_hash.items()
        }
        for future in as_completed(futures):
            image_hash = futures[future]
            try:
                results_by_hash[image_hash] = future.result()
            except TimeoutError as exc:
                results_by_hash[image_hash] = OcrResult.error("timeout", str(exc) or "OCR timed out")
            except Exception as exc:
                results_by_hash[image_hash] = OcrResult.error("provider_error", _short_error(exc))

    return {asset_id: results_by_hash[image_hash] for asset_id, image_hash in image_hashes.items()}


def _invoke_provider(provider: object, image_bytes: bytes, timeout: float | None) -> OcrResult:
    method: Any = getattr(provider, "extract_result", None)
    if callable(method):
        kwargs: dict[str, object] = {}
        try:
            parameters = inspect.signature(method).parameters
            if "timeout" in parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
            ):
                kwargs["timeout"] = timeout
        except (TypeError, ValueError):
            pass
        value = method(image_bytes, **kwargs)
    else:
        extract = getattr(provider, "extract", None)
        if not callable(extract):
            return OcrResult.error("invalid_provider", "OCR provider has no extract method")
        value = extract(image_bytes)
    return _coerce_result(value)


def _coerce_result(value: object) -> OcrResult:
    if isinstance(value, OcrResult):
        return value
    if isinstance(value, str):
        return OcrResult.from_text(value)
    if isinstance(value, Mapping):
        raw_status = value.get("status", "")
        status = raw_status.value if isinstance(raw_status, OcrStatus) else str(raw_status)
        text = value.get("text", "")
        error_code = value.get("error_code")
        error_message = value.get("error_message")
        if status == OcrStatus.SUCCESS.value:
            if error_code is not None or error_message is not None:
                return OcrResult.error("invalid_result", "successful OCR result contained error fields")
            if not isinstance(text, str) or not text.strip():
                return OcrResult.error("invalid_result", "successful OCR result did not contain text")
            return OcrResult.from_text(text)
        if status == OcrStatus.EMPTY.value:
            if error_code is not None or error_message is not None:
                return OcrResult.error("invalid_result", "empty OCR result contained error fields")
            if not isinstance(text, str) or text:
                return OcrResult.error("invalid_result", "empty OCR result contained text")
            return OcrResult(OcrStatus.EMPTY)
        if status == OcrStatus.ERROR.value:
            if not isinstance(text, str) or text:
                return OcrResult.error("invalid_result", "failed OCR result contained text")
            if not isinstance(error_code, str) or not error_code.strip():
                return OcrResult.error("invalid_result", "failed OCR result did not contain an error_code")
            if error_message is not None and not isinstance(error_message, str):
                return OcrResult.error("invalid_result", "failed OCR result contained a non-string error_message")
            return OcrResult.error(error_code, error_message)
    return OcrResult.error("invalid_result", "OCR provider returned an unsupported result")


def _short_error(error: BaseException) -> str:
    return (str(error).strip() or error.__class__.__name__)[:300]


__all__ = ["run_ocr_batch"]
