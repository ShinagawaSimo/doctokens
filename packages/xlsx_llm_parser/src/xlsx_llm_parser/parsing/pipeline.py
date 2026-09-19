"""Density-specific XLSX orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..models import ParsedWorkbook
from ..plan import XlsxParsePlan

Renderer = Callable[[ParsedWorkbook, int], Iterator[str]]


@dataclass(frozen=True, slots=True)
class XlsxRenderPipeline:
    """One immutable output pipeline for an XLSX density."""

    density: str
    plan: XlsxParsePlan
    renderer: Renderer

    def render(self, workbook: ParsedWorkbook, start_row: int = 1) -> Iterator[str]:
        return self.renderer(workbook, start_row)


def _render(workbook: ParsedWorkbook, density: str, start_row: int = 1) -> Iterator[str]:
    from ..rendering.structural import iter_workbook

    if start_row != 1:
        raise ValueError("start_row is not supported by the public XLSX API")
    return iter_workbook(workbook, density=density)


def _render_plain(workbook: ParsedWorkbook, start_row: int = 1) -> Iterator[str]:
    return _render(workbook, "plain", start_row)


def _render_structural(workbook: ParsedWorkbook, start_row: int = 1) -> Iterator[str]:
    return _render(workbook, "structural", start_row)


def _render_semantic(workbook: ParsedWorkbook, start_row: int = 1) -> Iterator[str]:
    return _render(workbook, "semantic", start_row)


_PIPELINES = {
    "plain": XlsxRenderPipeline("plain", XlsxParsePlan.render("plain"), _render_plain),
    "structural": XlsxRenderPipeline("structural", XlsxParsePlan.render("structural"), _render_structural),
    "semantic": XlsxRenderPipeline("semantic", XlsxParsePlan.render("semantic"), _render_semantic),
}


def get_render_pipeline(density: str) -> XlsxRenderPipeline:
    """Resolve a fixed pipeline once at the public API boundary."""
    try:
        return _PIPELINES[density]
    except KeyError as exc:
        raise ValueError(f"Invalid density {density!r}; expected one of {sorted(_PIPELINES)}") from exc


__all__ = ["XlsxRenderPipeline", "get_render_pipeline"]
