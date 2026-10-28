"""Density-specific XLSX orchestration."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from doctokens_core.output.plain import render_plain

from ..model.workbook import ParsedWorkbook
from ..rendering.dtx import iter_dtx
from ..rendering.plain import iter_plain
from .plan import XlsxParsePlan


@dataclass(frozen=True, slots=True)
class XlsxRenderPipeline:
    """One immutable output pipeline for an XLSX density."""

    density: str
    plan: XlsxParsePlan

    def render(self, workbook: ParsedWorkbook, start_row: int = 1) -> Iterator[str]:
        if self.density == "plain":
            content = "".join(iter_plain(workbook))
            return iter((render_plain(content, format_name="xlsx"),))
        if start_row != 1:
            raise ValueError("start_row is not supported by the public XLSX API")
        return iter_dtx(workbook, self.density)


_PIPELINES = {
    "plain": XlsxRenderPipeline("plain", XlsxParsePlan.render("plain")),
    "structural": XlsxRenderPipeline("structural", XlsxParsePlan.render("structural")),
    "semantic": XlsxRenderPipeline("semantic", XlsxParsePlan.render("semantic")),
}


def get_render_pipeline(density: str) -> XlsxRenderPipeline:
    """Resolve a fixed pipeline once at the public API boundary."""
    try:
        return _PIPELINES[density]
    except KeyError as exc:
        raise ValueError(f"Invalid density {density!r}; expected one of {sorted(_PIPELINES)}") from exc


__all__ = ["XlsxRenderPipeline", "get_render_pipeline"]
