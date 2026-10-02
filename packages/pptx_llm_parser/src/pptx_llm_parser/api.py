"""Public PPTX parsing and explicit read-session API."""

from __future__ import annotations

from collections.abc import Iterator

from ooxml_llm_core.models import Density, ParseReport, ParseResult, ResourceDescriptor
from ooxml_llm_core.session import SessionLifecycle

from ._api_support import Source, _density, _resource_descriptors, _result, _select_slides
from .core.enums import ResourceType
from .core.models import ParsedPresentation, ParseOptions
from .core.package import PackageReader
from .parsing import get_render_pipeline
from .parsing.runner import PptxParser
from .plan import PptxParsePlan
from .rendering.resources import render_resource


class PptxReadSession:
    """Context-managed PPTX session with one package reader owner."""

    def __init__(self, source: Source, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed_presentation: ParsedPresentation | None = None
        self._package_reader: PackageReader | None = None
        self._lifecycle: SessionLifecycle[ParsedPresentation] = SessionLifecycle("PPTX")

    def __enter__(self) -> PptxReadSession:
        self._lifecycle.check_new()
        self._package_reader = PackageReader(self.source, self.options)
        package = self._package_reader
        try:
            self.parsed_presentation = self._lifecycle.enter(
                package, lambda: PptxParser().parse(package, self.options, plan=PptxParsePlan.session())
            )
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._lifecycle.close()
        self._package_reader = None
        self.parsed_presentation = None

    def _require_open(self) -> ParsedPresentation:
        return self._lifecycle.require()

    @property
    def report(self) -> ParseReport:
        presentation = self._require_open()
        if presentation.report is None:  # pragma: no cover
            raise RuntimeError("parsed PPTX has no parse report")
        return presentation.report

    @property
    def resources(self) -> tuple[ResourceDescriptor, ...]:
        return _resource_descriptors(self._require_open())

    def describe(self) -> dict[str, object]:
        presentation = self._require_open()
        return {
            "format": "pptx",
            "report": self.report.to_dict(),
            "navigation": {
                "kind": "slides",
                "slide_count": len(presentation.slides),
                "slides": [{"number": s["n"], "hidden": s["hidden"], "section": s.get("section")} for s in presentation.slides],
            },
        }

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
            syntax_version="doctokens-xml/1.0",
            media_type="application/xml",
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
