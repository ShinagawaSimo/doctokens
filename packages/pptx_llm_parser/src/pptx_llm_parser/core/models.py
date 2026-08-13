"""PPTX parse models: options and parsed presentation structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from ooxml_llm_core.models import ParseWarning

DEFAULT_MAX_ZIP_ENTRIES = 10_000
DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class ParseOptions:
    """Tunables for a single parse. Frozen so callers can share one instance safely."""

    debug: bool = False
    output_dir: Path = field(default_factory=lambda: Path("out"))
    max_zip_entries: int = DEFAULT_MAX_ZIP_ENTRIES
    max_entry_uncompressed_bytes: int = DEFAULT_MAX_ENTRY_UNCOMPRESSED_BYTES
    max_total_uncompressed_bytes: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES

    def __post_init__(self) -> None:
        for name in (
            "max_zip_entries",
            "max_entry_uncompressed_bytes",
            "max_total_uncompressed_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")


class SlideBlock(TypedDict):
    """One slide in presentation order (sldIdLst)."""

    id: str
    type: str
    n: int
    part: str
    sldId: str
    hidden: bool
    text: list[str]


@dataclass
class ParsedPresentation:
    """All parse products for one presentation."""

    slides: list[SlideBlock] = field(default_factory=list)
    slide_size: tuple[int, int] | None = None
    warnings: list[ParseWarning] = field(default_factory=list)
