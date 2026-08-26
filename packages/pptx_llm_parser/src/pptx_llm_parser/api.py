"""Convenience functions — accept source files directly, return rendered results."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

from ooxml_llm_core.models import ParseReport, ParseWarning
from ooxml_llm_core.relationships import RelationshipIndex

from .core.enums import Density, ResourceType
from .core.models import ParsedPresentation, ParseOptions, SlideBlock
from .core.package import PackageReader
from .extractors.assets import AssetExtractor
from .extractors.objects import EmbeddedObjectExtractor
from .parser import PptxParser
from .plan import PptxParsePlan
from .renderers._render import (
    _html_comments_block,
    _html_slide_block,
    _plain_comments_block,
    _plain_slide_body,
    iter_plain,
    iter_semantic,
    iter_structural,
)
from .renderers.resources import render_resource


class PptxReadSession:
    """Context-managed PPTX facade for repeated downstream operations."""

    def __init__(self, source: str | Path | bytes, options: ParseOptions) -> None:
        self.source = source
        self.options = options
        self.parsed: ParsedPresentation | None = None
        self._package: PackageReader | None = None

    def __enter__(self) -> PptxReadSession:
        self._package = PackageReader(self.source, _without_ocr(self.options))
        self._package.__enter__()
        try:
            self.parsed = PptxParser().parse(self.source, self.options, plan=PptxParsePlan.session())
        except BaseException:  # pragma: no cover - defensive cleanup after a failed parse
            self._package.__exit__(None, None, None)
            self._package = None
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._package is not None:
            self._package.__exit__(exc_type, exc, traceback)
            self._package = None

    def _require_parsed(self) -> ParsedPresentation:
        if self.parsed is None:
            raise RuntimeError("PptxReadSession must be used as a context manager")
        return self.parsed

    @property
    def report(self) -> ParseReport:
        report = self._require_parsed().report
        if report is None:  # pragma: no cover - parser always attaches reports
            raise RuntimeError("parsed PPTX has no parse report")
        return report

    def render(self, *, density: Density | str = Density.SEMANTIC) -> str:
        parsed = self._require_parsed()
        resolved = Density.parse(density)
        if resolved is Density.PLAIN:
            return "".join(iter_plain(parsed))
        if resolved is Density.STRUCTURAL:
            return "".join(iter_structural(parsed))
        return "".join(iter_semantic(parsed))

    def iter_render(self, *, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
        parsed = self._require_parsed()
        resolved = Density.parse(density)
        if resolved is Density.PLAIN:
            return iter_plain(parsed)
        if resolved is Density.STRUCTURAL:
            return iter_structural(parsed)
        return iter_semantic(parsed)

    def render_window(self, *, slide: int, span: int = 1, density: Density | str = Density.SEMANTIC) -> str:
        parsed = self._require_parsed()
        resolved = Density.parse(density)
        if isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1:
            raise ValueError("slide must be -1 or a positive integer")
        if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
            raise ValueError("span must be a positive integer")
        start = len(parsed.slides) + slide if slide < 0 else slide - 1
        start = max(0, min(start, len(parsed.slides)))
        filtered = dataclasses.replace(parsed, slides=parsed.slides[start : start + span])
        if not filtered.slides:
            filtered.comments = []
        if resolved is Density.PLAIN:
            return "".join(iter_plain(filtered))
        if resolved is Density.STRUCTURAL:
            return "".join(iter_structural(filtered))
        return "".join(iter_semantic(filtered))

    def get_resource(
        self,
        resource_type: ResourceType | str,
        resource_id: str,
        *,
        rows: str | None = None,
        columns: list[int] | None = None,
        aggregate: str | None = None,
        aggregate_column: int | None = None,
    ) -> str | None:
        resolved = ResourceType.parse(resource_type)
        if resolved.is_plural:
            raise ValueError("resource_type must be singular, e.g. 'image' not 'images'")
        return render_resource(
            self._require_parsed(),
            self._package if resolved in (ResourceType.IMAGE, ResourceType.MEDIA) else None,
            resolved,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )


def open_pptx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> PptxReadSession:
    """Return an explicit context-managed PPTX read session."""
    return PptxReadSession(source, options or ParseOptions())


def parse_pptx(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse a PPTX file into LLM-readable markup."""
    resolved = Density.parse(density)
    if stream:
        return iter_slides(source, density=resolved, options=options)
    opts = options or ParseOptions()
    parsed = PptxParser().parse(
        source,
        opts if resolved is Density.SEMANTIC else _without_ocr(opts),
        plan=PptxParsePlan.render(resolved),
    )
    if resolved == Density.PLAIN:
        return "".join(iter_plain(parsed))
    if resolved == Density.STRUCTURAL:
        return "".join(iter_structural(parsed))
    return "".join(iter_semantic(parsed))


def iter_slides(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    start_slide: int = 1,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Yield rendered output chunks after the presentation has been parsed."""
    resolved = Density.parse(density)
    opts = options or ParseOptions()
    if isinstance(start_slide, bool) or not isinstance(start_slide, int) or start_slide < 1:
        raise ValueError("start_slide must be greater than zero")
    parsed = PptxParser().parse(
        source,
        opts if resolved is Density.SEMANTIC else _without_ocr(opts),
        plan=PptxParsePlan.render(resolved),
    )
    first_slide = True
    selected_slides = parsed.slides[start_slide - 1 :]
    for slide in selected_slides:
        if resolved is Density.PLAIN:
            parts: list[str] = []
            if first_slide:
                parts.append("density=plain\n")
                first_slide = False
            else:
                parts.append("\n")
            parts.append(f"=== Slide {slide['n']} ===\n")
            parts.append(_plain_slide_body(slide))
            yield "".join(parts)
            continue
        smartart_nodes = {smartart["id"]: smartart for smartart in parsed.smartarts}
        block = _html_slide_block(
            slide,
            smartart_nodes,
            semantic=resolved is Density.SEMANTIC,
            ocr_results=parsed.ocr_results if resolved is Density.SEMANTIC else None,
        )
        if first_slide:
            yield f"density={resolved.value}\n{block}"
            first_slide = False
        else:
            yield block
    if not selected_slides:
        return
    comments = _html_comments_block(parsed)
    if resolved is Density.PLAIN:
        comments = _plain_comments_block(parsed)
    if comments and parsed.comments:
        yield comments


def render_window(
    source: str | Path | bytes,
    *,
    slide: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Render a window of slides. slide is 1-based; slide=-1 selects the last slide."""
    resolved = Density.parse(density)
    if isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1:
        raise ValueError("slide must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    opts = options or ParseOptions()
    parsed = PptxParser().parse(source, _without_ocr(opts), plan=PptxParsePlan.render(resolved))
    start = len(parsed.slides) + slide if slide < 0 else slide - 1
    start = max(0, min(start, len(parsed.slides)))
    filtered = dataclasses.replace(parsed, slides=parsed.slides[start : start + span])
    if resolved is Density.SEMANTIC:
        _apply_selected_ocr(source, filtered, filtered.slides, opts)
    if not filtered.slides:
        filtered.comments = []  # empty selection renders as an empty document
    if resolved == Density.PLAIN:
        return "".join(iter_plain(filtered))
    if resolved == Density.STRUCTURAL:
        return "".join(iter_structural(filtered))
    return "".join(iter_semantic(filtered))


def get_resource(
    source: str | Path | bytes,
    resource_type: ResourceType | str,
    resource_id: str,
    *,
    rows: str | None = None,
    columns: list[int] | None = None,
    aggregate: str | None = None,
    aggregate_column: int | None = None,
    options: ParseOptions | None = None,
) -> str | None:
    """Extract one resource by id: image/media bytes (base64), full chart/smartart/table records."""
    resolved = ResourceType.parse(resource_type)
    if resolved.is_plural:
        raise ValueError("resource_type must be singular, e.g. 'image' not 'images'")
    opts = options or ParseOptions()
    if resolved in (ResourceType.IMAGE, ResourceType.MEDIA, ResourceType.CHART, ResourceType.SMARTART):
        warnings: list[ParseWarning] = []
        with PackageReader(source, _without_ocr(opts)) as pkg:
            pkg.validate()
            relationships = RelationshipIndex.from_records(pkg.read_all_relationships())
            if resolved in (ResourceType.IMAGE, ResourceType.MEDIA):
                assets, _ = AssetExtractor(pkg, relationships, warnings).extract()
                parsed = ParsedPresentation(assets=assets, warnings=warnings)
            else:
                objects = EmbeddedObjectExtractor(pkg, relationships, warnings)
                if resolved is ResourceType.CHART:
                    chart = objects.chart_by_id(resource_id)
                    parsed = ParsedPresentation(charts=[chart] if chart is not None else [], warnings=warnings)
                else:
                    smartart = objects.smartart_by_id(resource_id)
                    parsed = ParsedPresentation(smartarts=[smartart] if smartart is not None else [], warnings=warnings)
            return render_resource(
                parsed,
                pkg,
                resolved,
                resource_id,
            )
    if resolved is ResourceType.TABLE:
        iterator = PptxParser().iter_slides(source, _without_ocr(opts))
        try:
            for _slide, parsed in iterator:
                if any(shape["type"] == "table" and shape.get("tableId") == resource_id for shape in parsed.slides[0]["shapes"]):
                    return render_resource(
                        parsed,
                        None,
                        resolved,
                        resource_id,
                        rows=rows,
                        columns=columns,
                        aggregate=aggregate,
                        aggregate_column=aggregate_column,
                    )
            return None
        finally:
            iterator.close()
    parsed = PptxParser().parse(source, _without_ocr(opts), plan=PptxParsePlan.resource(resolved))
    return render_resource(
        parsed,
        None,
        resolved,
        resource_id,
        rows=rows,
        columns=columns,
        aggregate=aggregate,
        aggregate_column=aggregate_column,
    )


def _without_ocr(options: ParseOptions) -> ParseOptions:
    return dataclasses.replace(options, ocr=None) if options.ocr is not None else options


def _apply_selected_ocr(
    source: str | Path | bytes,
    parsed: ParsedPresentation,
    slides: list[SlideBlock],
    options: ParseOptions,
) -> None:  # pragma: no cover - OCR provider execution is covered at the adapter boundary
    if options.ocr is None:
        return
    with PackageReader(source, options) as pkg:
        parsed.ocr_results = PptxParser._run_ocr(
            pkg,
            parsed.assets,
            slides,
            options,
        )
