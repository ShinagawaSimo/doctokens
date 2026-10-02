"""Public PPTX parsing and explicit read-session API."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from ooxml_llm_core.models import Density, ParseResult, ResourceDescriptor

from .core.models import ParsedPresentation

Source = str | Path | bytes


def _density(value: Density | str) -> Density:
    if value not in {"plain", "structural", "semantic"}:
        raise ValueError("density must be one of: 'plain', 'structural', 'semantic'")
    return value


def _resource_descriptors(presentation: ParsedPresentation) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for asset in presentation.assets:
        source = "external" if asset.get("source") == "external" else "embedded"
        descriptors.append(
            ResourceDescriptor(
                id=asset["id"],
                kind=str(asset.get("type", "image")),
                source=source,  # type: ignore[arg-type]
                locator=asset.get("zipPath") or asset.get("href") or asset["id"],
                content_type=asset.get("contentType"),
                part=asset.get("zipPath"),
                external_target=asset.get("href"),
            )
        )
    for chart in presentation.charts:
        descriptors.append(  # noqa: PERF401
            ResourceDescriptor(chart["id"], "chart", "embedded", chart.get("part", chart["id"]), part=chart.get("part"))
        )
    for smartart in presentation.smartarts:
        descriptors.append(  # noqa: PERF401
            ResourceDescriptor(
                smartart["id"],
                "smartart",
                "embedded",
                smartart.get("part", smartart["id"]),
                part=smartart.get("part"),
            )
        )
    for slide in presentation.slides:
        for shape in slide["shapes"]:
            table_id = shape.get("tableId")
            if shape.get("type") == "table" and table_id:
                descriptors.append(ResourceDescriptor(table_id, "table", "embedded", slide["part"], part=slide["part"]))
    return tuple(descriptors)


def _result(
    presentation: ParsedPresentation,
    text: str,
    density: Density,
    selection: dict[str, object],
    *,
    syntax_version: str | None = None,
    media_type: str | None = None,
) -> ParseResult:
    if presentation.report is None:  # pragma: no cover - parser always attaches a report
        raise RuntimeError("parsed PPTX has no parse report")
    resolved_syntax, resolved_media_type = _output_metadata(density)
    return ParseResult(
        text,
        density,
        selection,
        presentation.report,
        _resource_descriptors(presentation),
        syntax_version or resolved_syntax,
        media_type or resolved_media_type,
    )


def _output_metadata(density: Density) -> tuple[str, str]:
    if density == "plain":
        return "doctokens-plain/1.0", "text/plain"
    return "doctokens-xml/1.0", "application/xml"


def _select_slides(
    presentation: ParsedPresentation,
    slide: int | None,
    span: int,
) -> tuple[ParsedPresentation, dict[str, object]]:
    if slide is not None and (isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1):
        raise ValueError("slide must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    if slide is None:
        if span != 1:
            raise ValueError("span requires slide")
        return presentation, {"kind": "all"}

    start = len(presentation.slides) + slide if slide < 0 else slide - 1
    if start < 0 or start >= len(presentation.slides):
        return dataclasses.replace(presentation, slides=[], comments=[]), {
            "kind": "slide",
            "start": slide,
            "span": span,
            "empty": True,
        }
    selected = presentation.slides[start : start + span]
    selected_ids = {item["id"] for item in selected}
    comments = [item for item in presentation.comments if item.get("slideId") in selected_ids]
    return dataclasses.replace(presentation, slides=selected, comments=comments), {
        "kind": "slide",
        "start": start + 1,
        "span": span,
    }
