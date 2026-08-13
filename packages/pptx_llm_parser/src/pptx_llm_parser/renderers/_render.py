"""Main rendering iterators for the three densities (M1: plain only)."""

from __future__ import annotations

from collections.abc import Iterator

from ..core.models import ParsedPresentation


def iter_plain(parsed: ParsedPresentation) -> Iterator[str]:
    """plain — pure text stream with slide separators."""
    yield "density=plain\n"
    for slide in parsed.slides:
        if slide["n"] > 1:
            yield "\n"
        yield f"=== Slide {slide['n']} ===\n"
        yield "\n\n".join(slide["text"])
