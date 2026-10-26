"""Run the optional DOCX image OCR adapter in bounded, deduplicated batches."""

from __future__ import annotations

from typing import cast

from ..model import ImageAsset, OcrStoredResult, ParseOptions
from ..ooxml.package import PackageReader

_MAX_OCR_BATCH_BYTES = 64 * 1024 * 1024


def run_ocr(
    package: PackageReader,
    assets: list[ImageAsset],
    parse_options: ParseOptions,
) -> dict[str, OcrStoredResult]:
    """Run fail-soft OCR in bounded batches, reusing shared media parts."""
    provider = getattr(parse_options, "ocr", None)
    if provider is None:
        return {}

    asset_ids_by_path: dict[str, list[str]] = {}
    for asset in assets:
        if asset["type"] != "image" or asset.get("source") != "embedded":
            continue
        zip_path = asset.get("zipPath")
        if not zip_path:
            continue
        asset_ids_by_path.setdefault(zip_path, []).append(asset["id"])

    from ocr_llm_core import OcrResult, run_ocr_batch

    results: dict[str, OcrStoredResult] = {}
    pending: dict[str, bytes] = {}
    aliases: dict[str, list[str]] = {}
    pending_bytes = 0
    item_limit = max(1, parse_options.ocr_workers * 2)

    def flush() -> None:
        nonlocal pending_bytes
        batch_results = run_ocr_batch(
            pending,
            provider,
            max_workers=parse_options.ocr_workers,
            timeout=parse_options.ocr_timeout,
        )
        for primary_id, ocr_result in batch_results.items():
            record = ocr_result.to_record()
            for asset_id in aliases[primary_id]:
                results[asset_id] = cast(OcrStoredResult, dict(record))
        pending.clear()
        aliases.clear()
        pending_bytes = 0

    for zip_path, asset_ids in asset_ids_by_path.items():
        try:
            with package.open_entry(zip_path) as stream:
                image_bytes = stream.read()
        except Exception as exc:
            record = OcrResult.error("image_read_error", str(exc)).to_record()
            for asset_id in asset_ids:
                results[asset_id] = cast(OcrStoredResult, dict(record))
            continue
        if pending and (len(pending) >= item_limit or pending_bytes + len(image_bytes) > _MAX_OCR_BATCH_BYTES):
            flush()
        primary_id = asset_ids[0]
        pending[primary_id] = image_bytes
        aliases[primary_id] = asset_ids
        pending_bytes += len(image_bytes)
    if pending:
        flush()
    return results
