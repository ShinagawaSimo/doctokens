"""Shared parser options for OPC-based document readers."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PackageOptions:
    """Common package limits.

    Format parsers extend this type with format-specific switches.  The base
    class deliberately contains no cache or document lifecycle state.
    """

    max_zip_entries: int = 10_000
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024

    def validate_package_options(self) -> None:
        for name in (
            "max_zip_entries",
            "max_entry_uncompressed_bytes",
            "max_total_uncompressed_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be greater than zero")

    @staticmethod
    def validate_ocr_options(ocr: object | None, workers: int, timeout: float) -> None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
            raise ValueError("ocr_workers must be greater than zero")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("ocr_timeout must be greater than zero")
        if ocr is not None and not any(callable(getattr(ocr, method, None)) for method in ("extract", "extract_result")):
            raise TypeError("ocr must provide an extract(image_bytes) or extract_result(image_bytes) method")


__all__ = ["PackageOptions"]
