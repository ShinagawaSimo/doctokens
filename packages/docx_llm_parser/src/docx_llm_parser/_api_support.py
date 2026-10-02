"""Public DOCX parsing and explicit read-session API."""

from __future__ import annotations

from pathlib import Path

from ooxml_llm_core.models import Density, ParseResult, ResourceDescriptor

from .core.models import ParsedDocument
from .rendering.objects.resources import table_groups

Source = str | Path | bytes


def _density(value: Density | str) -> Density:
    if value not in {"plain", "structural", "semantic"}:
        raise ValueError("density must be one of: 'plain', 'structural', 'semantic'")
    return value


def _validate_window(page_hint: int | None, span: int) -> None:
    if page_hint is not None and (
        isinstance(page_hint, bool) or not isinstance(page_hint, int) or page_hint == 0 or page_hint < -1
    ):
        raise ValueError("page_hint must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    if page_hint is None and span != 1:
        raise ValueError("span requires page_hint")


def _resource_descriptors(document: ParsedDocument) -> tuple[ResourceDescriptor, ...]:
    descriptors: list[ResourceDescriptor] = []
    for asset in document.assets:
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
    descriptors.extend(
        ResourceDescriptor(chart["id"], "chart", "embedded", chart.get("part", chart["id"]), part=chart.get("part"))
        for chart in document.charts
    )
    descriptors.extend(
        ResourceDescriptor(
            smartart["id"],
            "smartart",
            "embedded",
            smartart.get("part", smartart["id"]),
            part=smartart.get("part"),
        )
        for smartart in document.smartarts
    )
    descriptors.extend(ResourceDescriptor(table_id, "table", "embedded", table_id) for table_id in table_groups(document))
    return tuple(descriptors)


def _result(
    document: ParsedDocument,
    text: str,
    density: Density,
    selection: dict[str, object],
    *,
    syntax_version: str | None = None,
    media_type: str | None = None,
) -> ParseResult:
    if document.report is None:  # pragma: no cover - parser always attaches a report
        raise RuntimeError("parsed DOCX has no parse report")
    resolved_syntax, resolved_media_type = _output_metadata(density)
    return ParseResult(
        text,
        density,
        selection,
        document.report,
        _resource_descriptors(document),
        syntax_version or resolved_syntax,
        media_type or resolved_media_type,
    )


def _output_metadata(density: Density) -> tuple[str, str]:
    if density == "plain":
        return "doctokens-plain/1.0", "text/plain"
    return "doctokens-xml/1.0", "application/xml"
