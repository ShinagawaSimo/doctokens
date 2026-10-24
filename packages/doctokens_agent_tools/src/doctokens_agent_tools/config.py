"""Host-owned resource limits and OCR configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from doctokens_core.options import PackageOptions


@dataclass(frozen=True)
class RuntimeConfig:
    allowed_roots: tuple[Path, ...]
    max_sessions: int = 4
    max_documents: int = 32
    idle_seconds: float = 600
    max_result_bytes: int = 64 * 1024 * 1024
    result_idle_seconds: float = 600
    reply_chars: int = 12_000
    result_chunk_chars: int = 8_000
    max_chunk_size: int = 32_000
    max_inline_binary_bytes: int = 256 * 1024
    max_snapshot_bytes: int = 128 * 1024 * 1024
    max_snapshot_total_bytes: int = 512 * 1024 * 1024
    workers: int = 2
    package_options: PackageOptions = field(default_factory=PackageOptions)
    ocr_provider: object | None = None
    ocr_workers: int = 4
    ocr_timeout: float = 120
    max_session_memory_bytes: int = 256 * 1024 * 1024
    max_session_total_memory_bytes: int = 512 * 1024 * 1024
    mcp_output_mode: Literal["compatible", "compact"] = "compatible"
    max_search_bytes: int = 32 * 1024 * 1024
    max_search_states: int = 8
    search_idle_seconds: float = 600

    def __post_init__(self) -> None:
        if not self.allowed_roots:
            raise ValueError("at least one allowed root is required")
        roots = tuple(Path(root).resolve(strict=True) for root in self.allowed_roots)
        if any(not root.is_dir() for root in roots):
            raise ValueError("allowed roots must be directories")
        object.__setattr__(self, "allowed_roots", roots)
        for name in (
            "max_sessions",
            "max_session_memory_bytes",
            "max_session_total_memory_bytes",
            "max_documents",
            "max_result_bytes",
            "reply_chars",
            "result_chunk_chars",
            "max_chunk_size",
            "max_inline_binary_bytes",
            "max_snapshot_bytes",
            "max_snapshot_total_bytes",
            "workers",
            "max_search_bytes",
            "max_search_states",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("idle_seconds", "result_idle_seconds", "search_idle_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.reply_chars < 4:
            raise ValueError("reply_chars must be at least 4 to encode binary fragments")
        if self.mcp_output_mode not in {"compatible", "compact"}:
            raise ValueError("mcp_output_mode must be compatible or compact")
        self.package_options.validate_package_options()
        self.package_options.validate_ocr_options(self.ocr_provider, self.ocr_workers, self.ocr_timeout)
