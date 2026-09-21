"""Public PPTX parsing and explicit read-session API."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

from ooxml_llm_core.models import Density, ParseReport, ParseResult, ResourceDescriptor

from .core.enums import ResourceType
from .core.models import ParsedPresentation, ParseOptions
from .core.package import PackageReader
from .parsing import get_render_pipeline
from .parsing.runner import PptxParser
from .plan import PptxParsePlan
from .rendering.resources import render_resource

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


class PptxReadSession:
    """Context-managed PPTX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed_presentation: ParsedPresentation | None = None
        self._package_reader: PackageReader | None = None
        self._state = "new"

    def __enter__(self) -> PptxReadSession:
        if self._state != "new":
            raise RuntimeError("PPTX session cannot be entered twice")
        self._package_reader = PackageReader(self.source, self.options)
        try:
            self._package_reader.__enter__()
            self.parsed_presentation = PptxParser().parse(
                self._package_reader,
                self.options,
                plan=PptxParsePlan.session(),
            )
        except BaseException:
            self.close()
            raise
        self._state = "open"
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._state == "closed":
            return
        if self._package_reader is not None:
            self._package_reader.__exit__(None, None, None)
            self._package_reader = None
        self.parsed_presentation = None
        self._state = "closed"

    def _require_open(self) -> ParsedPresentation:
        if self._state != "open" or self.parsed_presentation is None:
            raise RuntimeError("PPTX session is not open")
        return self.parsed_presentation

    @property
    def report(self) -> ParseReport:
        presentation = self._require_open()
        if presentation.report is None:  # pragma: no cover
            raise RuntimeError("parsed PPTX has no parse report")
        return presentation.report

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

    def render(
        self,
        *,
        density: Density | str = "semantic",
        slide: int | None = None,
        span: int = 1,
    ) -> ParseResult:
        presentation = self._require_open()
        resolved = _density(density)
        selected, selection = _select_slides(presentation, slide, span)
        text = "".join(get_render_pipeline(resolved).render(selected))
        return _result(presentation, text, resolved, selection)

    def iter_render(
        self,
        *,
        density: Density | str = "semantic",
        slide: int | None = None,
        span: int = 1,
    ) -> Iterator[str]:
        presentation = self._require_open()
        resolved = _density(density)
        selected, _selection = _select_slides(presentation, slide, span)
        chunks = get_render_pipeline(resolved).render(selected)

        def guarded() -> Iterator[str]:
            for chunk in chunks:
                self._require_open()
                yield chunk

        return guarded()

    def read_resource(self, kind: str, resource_id: str) -> bytes:
        presentation = self._require_open()
        if kind not in {"image", "media"}:
            raise ValueError("PPTX binary resources support only 'image' and 'media'")
        descriptor = next(
            (item for item in _resource_descriptors(presentation) if item.kind == kind and item.id == resource_id),
            None,
        )
        if descriptor is None:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        if descriptor.source == "external":
            raise ValueError("external PPTX resources are not downloaded")
        if descriptor.part is None or self._package_reader is None:
            raise RuntimeError("PPTX package reader is not open")
        return self._package_reader.read_part(descriptor.part)

    def render_resource(
        self,
        kind: str,
        resource_id: str,
        *,
        rows: str | None = None,
        columns: list[int] | None = None,
        aggregate: str | None = None,
        aggregate_column: int | None = None,
    ) -> ParseResult:
        presentation = self._require_open()
        resolved = ResourceType.parse(kind)
        if resolved.is_plural:
            raise ValueError("resource kind must be singular")
        if resolved in (ResourceType.IMAGE, ResourceType.MEDIA):
            raise ValueError("use read_resource() for PPTX image or media bytes")
        text = render_resource(
            presentation,
            self._package_reader if resolved in (ResourceType.IMAGE, ResourceType.MEDIA) else None,
            resolved,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
        if text is None:
            raise KeyError(f"resource {kind!r}/{resource_id!r} not found")
        return _result(
            presentation,
            text,
            "semantic",
            {"kind": "resource", "resource_kind": kind, "id": resource_id},
            syntax_version="legacy-markup/0",
            media_type="text/plain",
        )


def open_pptx(source: Source, *, options: ParseOptions | None = None) -> PptxReadSession:
    return PptxReadSession(source, options or ParseOptions())


def parse_pptx(
    source: Source,
    *,
    density: Density | str = "semantic",
    slide: int | None = None,
    span: int = 1,
    options: ParseOptions | None = None,
) -> ParseResult:
    resolved = _density(density)
    selected_options = options or ParseOptions()
    pipeline = get_render_pipeline(resolved)
    presentation = PptxParser().parse(source, selected_options, plan=pipeline.plan)
    selected, selection = _select_slides(presentation, slide, span)
    return _result(presentation, "".join(pipeline.render(selected)), resolved, selection)


__all__ = ["PptxReadSession", "open_pptx", "parse_pptx"]
