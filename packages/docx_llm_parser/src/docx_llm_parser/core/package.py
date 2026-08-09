"""DOCX package reader — wraps shared OPC infrastructure via ooxml_llm_core."""

from __future__ import annotations

from pathlib import Path

from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.package import (
    PackageError,
    rels_path_for_part,
    resolve_relationship_target,
    source_part_from_rels_path,
)
from ooxml_llm_core.package import (
    PackageReader as _BasePackageReader,
)
from typing_extensions import Self

from .models import ParseOptions

# Backward-compatible alias for tests and existing code
DocxPackageError = PackageError

__all__ = [
    "DocxPackageError",
    "PackageError",
    "PackageReader",
    "rels_path_for_part",
    "resolve_relationship_target",
    "source_part_from_rels_path",
]


class PackageReader(_BasePackageReader):
    """DOCX-format OPC reader.

    Thin subclass that translates ParseOptions → PackageLimits and defaults
    ``validate()`` to require ``word/document.xml``.
    """

    def __init__(self, source: str | Path | bytes, options: ParseOptions) -> None:
        self.options = options
        super().__init__(
            source,
            PackageLimits(
                max_zip_entries=options.max_zip_entries,
                max_entry_uncompressed_bytes=options.max_entry_uncompressed_bytes,
                max_total_uncompressed_bytes=options.max_total_uncompressed_bytes,
            ),
        )

    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def validate(self, required_part: str | None = None) -> None:
        super().validate(required_part=required_part or "word/document.xml")
