"""Block-level rendering dispatcher (headings and tables only)."""

from __future__ import annotations

from collections.abc import Iterator, Set
from html import escape

from ...core.models import Block, ContentControl, OcrStoredResult
from ..common.controls import control_attrs, wrap_control
from ..inline import inline_content
from ..tables import render_table


def render_block(
    block: Block,
    density: str,
    ocr_results: dict[str, OcrStoredResult] | None = None,
    used_anchors: Set[str] | None = None,
) -> Iterator[str]:
    """Dispatch a parsed block to its density-specific renderer."""
    controls: list[ContentControl] = block.get("contentControls", [])
    if block["type"] == "heading":
        level = min(block["level"], 6)
        content = inline_content(block, density, ocr_results)
        if controls:
            content = wrap_control(content, controls, density)
        yield f"<h{level}{_anchor_attrs(block, used_anchors)}>{content}\n"
    elif block["type"] == "paragraph":
        content = inline_content(block, density, ocr_results)
        if controls:
            content = wrap_control(content, controls, density)
        yield f"<p{_anchor_attrs(block, used_anchors)}>{content}\n"
    else:
        if not controls:
            yield from render_table(block, density, ocr_results)
            return
        for control in controls:
            yield f"<control {control_attrs(control, density)}>\n"
        yield from render_table(block, density, ocr_results)
        for _control in reversed(controls):
            yield "</control>\n"


def _anchor_attrs(block: Block, used_anchors: Set[str] | None) -> str:
    anchors = block.get("anchors", []) if block["type"] in {"paragraph", "heading"} else []
    anchor = next((item for item in anchors if used_anchors is None or item in used_anchors), "")
    if not anchor:
        return ""
    return f" anchor={escape(anchor, quote=True)}"
