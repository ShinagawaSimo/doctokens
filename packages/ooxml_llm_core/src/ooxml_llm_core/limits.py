"""OPC package security limits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageLimits:
    """OPC ZIP entry security thresholds.

    These limits are shared across all format parsers that read OPC packages.
    """

    max_zip_entries: int = 10_000
    max_entry_uncompressed_bytes: int = 50_000_000   # 50 MiB
    max_total_uncompressed_bytes: int = 500_000_000  # 500 MiB

    def __post_init__(self) -> None:
        for name in (
            "max_zip_entries",
            "max_entry_uncompressed_bytes",
            "max_total_uncompressed_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
