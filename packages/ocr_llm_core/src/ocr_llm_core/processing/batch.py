"""Provider-agnostic OCR batching used by Office parsers."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from ..models import OcrResult


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
    if not callable(method):
        return OcrResult.error("invalid_provider", "OCR provider must implement extract_result")
    value = method(image_bytes, timeout=timeout)
    if not isinstance(value, OcrResult):
        return OcrResult.error("invalid_result", "OCR provider must return OcrResult")
    return value


def _short_error(error: BaseException) -> str:
    return (str(error).strip() or error.__class__.__name__)[:300]


__all__ = ["run_ocr_batch"]
