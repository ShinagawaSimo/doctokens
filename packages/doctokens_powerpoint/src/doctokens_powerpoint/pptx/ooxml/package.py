"""PPTX package reader — wraps shared OPC infrastructure via doctokens_core."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from doctokens_core.containers.opc.limits import PackageLimits
from doctokens_core.containers.opc.reader import PackageReader as _BasePackageReader

if TYPE_CHECKING:
    # Self only appears in annotations (lazy via __future__ annotations),
    # so typing_extensions is not a runtime dependency.
    from typing_extensions import Self

from ..model.presentation import ParseOptions

__all__ = [
    "PackageReader",
]


class PackageReader(_BasePackageReader):
    """PPTX-format OPC reader.

    Thin subclass that translates ParseOptions → PackageLimits and defaults
    ``validate()`` to require ``ppt/presentation.xml``.
    """

    def __init__(self, source: str | Path | bytes, options: ParseOptions, *, memory_limit_bytes: int | None = None) -> None:
        self.options = options
        super().__init__(
            source,
            PackageLimits(
                max_zip_entries=options.max_zip_entries,
                max_entry_uncompressed_bytes=options.max_entry_uncompressed_bytes,
                max_total_uncompressed_bytes=options.max_total_uncompressed_bytes,
            ),
            memory_limit_bytes=memory_limit_bytes,
        )

    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def validate(self, required_part: str | None = None) -> None:
        super().validate(required_part=required_part or "ppt/presentation.xml")
