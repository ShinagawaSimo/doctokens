"""Density-specific PPTX orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..core.enums import Density
from ..core.models import ParsedPresentation
from ..plan import PptxParsePlan
from ..rendering.plain import iter_plain
from ..rendering.semantic import iter_semantic
from ..rendering.structural import iter_structural

Renderer = Callable[[ParsedPresentation], Iterator[str]]


@dataclass(frozen=True, slots=True)
class PptxRenderPipeline:
    """One immutable output pipeline for a PPTX density."""

    density: Density
    plan: PptxParsePlan
    renderer: Renderer

    def render(self, parsed: ParsedPresentation) -> Iterator[str]:
        return self.renderer(parsed)


_PIPELINES = {
    Density.PLAIN: PptxRenderPipeline(Density.PLAIN, PptxParsePlan.render(Density.PLAIN), iter_plain),
    Density.STRUCTURAL: PptxRenderPipeline(
        Density.STRUCTURAL,
        PptxParsePlan.render(Density.STRUCTURAL),
        iter_structural,
    ),
    Density.SEMANTIC: PptxRenderPipeline(Density.SEMANTIC, PptxParsePlan.render(Density.SEMANTIC), iter_semantic),
}


def get_render_pipeline(density: Density | str) -> PptxRenderPipeline:
    """Resolve a fixed pipeline once at the public API boundary."""
    return _PIPELINES[Density.parse(density)]


__all__ = ["PptxRenderPipeline", "get_render_pipeline"]
