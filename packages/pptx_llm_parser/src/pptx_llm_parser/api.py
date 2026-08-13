"""Convenience functions — accept source files directly, return rendered results."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .core.enums import Density
from .core.models import ParseOptions
from .parser import PptxParser
from .renderers._render import iter_plain


def parse_pptx(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse a PPTX file into LLM-readable markup."""
    resolved = Density.parse(density)
    if stream:
        raise NotImplementedError("stream=True is not implemented yet")
    parsed = PptxParser().parse(source, options or ParseOptions())
    if resolved == Density.PLAIN:
        return "".join(iter_plain(parsed))
    raise NotImplementedError(f"density={resolved.value} is not implemented yet")
