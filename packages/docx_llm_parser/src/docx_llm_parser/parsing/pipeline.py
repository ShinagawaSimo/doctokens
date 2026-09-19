"""Density-specific DOCX orchestration.

The parser and renderer are selected once at the boundary.  Inner extractors
receive a concrete plan and do not need to branch on the output density.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..core.enums import Density
from ..core.models import ParsedDocument
from ..plan import DocxParsePlan
from ..rendering.plain.pipeline import iter_plain
from ..rendering.semantic import iter_semantic
from ..rendering.structural import iter_structural

Renderer = Callable[[ParsedDocument], Iterator[str]]


@dataclass(frozen=True, slots=True)
class DocxRenderPipeline:
    """One immutable output pipeline for a DOCX density."""

    density: Density
    plan: DocxParsePlan
    renderer: Renderer

    def render(self, parsed: ParsedDocument) -> Iterator[str]:
        return self.renderer(parsed)


_PIPELINES = {
    Density.PLAIN: DocxRenderPipeline(Density.PLAIN, DocxParsePlan.render(Density.PLAIN), iter_plain),
    Density.STRUCTURAL: DocxRenderPipeline(
        Density.STRUCTURAL,
        DocxParsePlan.render(Density.STRUCTURAL),
        iter_structural,
    ),
    Density.SEMANTIC: DocxRenderPipeline(Density.SEMANTIC, DocxParsePlan.render(Density.SEMANTIC), iter_semantic),
}


def get_render_pipeline(density: Density | str) -> DocxRenderPipeline:
    """Resolve a fixed pipeline once at the public API boundary."""
    return _PIPELINES[Density.parse(density)]


__all__ = ["DocxRenderPipeline", "get_render_pipeline"]
