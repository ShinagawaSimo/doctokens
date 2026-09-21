"""Density-specific PPTX orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial

from ooxml_llm_core.doctokens_plain import render_plain

from ..core.enums import Density
from ..core.models import ParsedPresentation
from ..plan import PptxParsePlan
from ..rendering.dtx import iter_dtx
from ..rendering.plain import iter_plain

Renderer = Callable[[ParsedPresentation], Iterator[str]]


@dataclass(frozen=True, slots=True)
class PptxRenderPipeline:
    """One immutable output pipeline for a PPTX density."""

    density: Density
    plan: PptxParsePlan
    renderer: Renderer

    def render(self, parsed: ParsedPresentation) -> Iterator[str]:
        if self.density is Density.PLAIN:
            legacy_text = "".join(self.renderer(parsed))
            return iter((render_plain(legacy_text, format_name="pptx"),))
        return self.renderer(parsed)


_PIPELINES = {
    Density.PLAIN: PptxRenderPipeline(Density.PLAIN, PptxParsePlan.render(Density.PLAIN), iter_plain),
    Density.STRUCTURAL: PptxRenderPipeline(
        Density.STRUCTURAL,
        PptxParsePlan.render(Density.STRUCTURAL),
        partial(iter_dtx, density="structural"),
    ),
    Density.SEMANTIC: PptxRenderPipeline(
        Density.SEMANTIC,
        PptxParsePlan.render(Density.SEMANTIC),
        partial(iter_dtx, density="semantic"),
    ),
}


def get_render_pipeline(density: Density | str) -> PptxRenderPipeline:
    """Resolve a fixed pipeline once at the public API boundary."""
    return _PIPELINES[Density.parse(density)]


__all__ = ["PptxRenderPipeline", "get_render_pipeline"]
