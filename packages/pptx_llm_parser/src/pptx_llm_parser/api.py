"""Public PPTX API for parsing, rendering, and resource extraction."""

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
    _plain_comments_block,
    _plain_slide_body,
    _render_comments_output,
    _render_slide_output,
    iter_plain,
    iter_semantic,
    iter_structural,
)
from .renderers.resources import render_resource


class PptxReadSession:
    """Context-managed facade for repeated operations on one parsed PPTX.

    The source is parsed on entering the context.  The session keeps the
    package reader open for resource reads that need binary media data and
    releases it when the context exits.
    """

    def __init__(self, source: str | Path | bytes, parse_options: ParseOptions) -> None:
        self.source = source
        self.parse_options = parse_options
        self.parsed_presentation: ParsedPresentation | None = None
        self._package_reader: PackageReader | None = None

    def __enter__(self) -> PptxReadSession:
        self._package_reader = PackageReader(self.source, _without_ocr(self.parse_options))
        self._package_reader.__enter__()
        try:
            self.parsed_presentation = PptxParser().parse(
                self.source,
                self.parse_options,
                plan=PptxParsePlan.session(),
            )
        except BaseException:  # pragma: no cover - defensive cleanup after a failed parse
            self._package_reader.__exit__(None, None, None)
            self._package_reader = None
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._package_reader is not None:
            self._package_reader.__exit__(exc_type, exc, traceback)
            self._package_reader = None

    def _require_parsed_presentation(self) -> ParsedPresentation:
        if self.parsed_presentation is None:
            raise RuntimeError("PptxReadSession must be used as a context manager")
        return self.parsed_presentation

    @property
    def report(self) -> ParseReport:
        """Return diagnostics collected while parsing the presentation."""
        report = self._require_parsed_presentation().report
        if report is None:  # pragma: no cover - parser always attaches reports
            raise RuntimeError("parsed PPTX has no parse report")
        return report

    def render(self, *, density: Density | str = Density.SEMANTIC) -> str:
        """Render the complete presentation at the requested output density.

        Args:
            density: ``plain`` for text only, ``structural`` for slide and
                object structure, or ``semantic`` for structure plus styling
                and metadata.  A :class:`Density` value may be supplied.

        Returns:
            The complete self-defined LLM output string.
        """
        parsed_presentation = self._require_parsed_presentation()
        output_density = Density.parse(density)
        if output_density is Density.PLAIN:
            return "".join(iter_plain(parsed_presentation))
        if output_density is Density.STRUCTURAL:
            return "".join(iter_structural(parsed_presentation))
        return "".join(iter_semantic(parsed_presentation))

    def iter_render(self, *, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
        """Yield complete-presentation output chunks at the requested density.

        Args:
            density: Output detail level.  Parsing has already completed;
                this method controls output iteration only.

        Returns:
            An iterator whose chunks concatenate to the value of :meth:`render`.
        """
        parsed_presentation = self._require_parsed_presentation()
        output_density = Density.parse(density)
        if output_density is Density.PLAIN:
            return iter_plain(parsed_presentation)
        if output_density is Density.STRUCTURAL:
            return iter_structural(parsed_presentation)
        return iter_semantic(parsed_presentation)

    def render_window(self, *, slide: int, span: int = 1, density: Density | str = Density.SEMANTIC) -> str:
        """Render a bounded slide window from the loaded presentation.

        Args:
            slide: One-based slide number.  ``-1`` selects the last slide.
            span: Number of consecutive slides to include; must be positive.
            density: Output detail level.

        Returns:
            Output for the selected slides.  An empty selection has no
            presentation comments attached.

        Raises:
            ValueError: If ``slide`` or ``span`` is invalid.
        """
        parsed_presentation = self._require_parsed_presentation()
        output_density = Density.parse(density)
        if isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1:
            raise ValueError("slide must be -1 or a positive integer")
        if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
            raise ValueError("span must be a positive integer")
        start_index = len(parsed_presentation.slides) + slide if slide < 0 else slide - 1
        start_index = max(0, min(start_index, len(parsed_presentation.slides)))
        selected_presentation = dataclasses.replace(
            parsed_presentation,
            slides=parsed_presentation.slides[start_index : start_index + span],
        )
        if not selected_presentation.slides:
            selected_presentation.comments = []
        if output_density is Density.PLAIN:
            return "".join(iter_plain(selected_presentation))
        if output_density is Density.STRUCTURAL:
            return "".join(iter_structural(selected_presentation))
        return "".join(iter_semantic(selected_presentation))

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
        """Return one resource from the loaded presentation.

        Args:
            resource_type: Singular resource kind, such as ``image``,
                ``media``, ``chart``, ``smartart``, or ``table``.
            resource_id: Resource identifier recorded in the presentation.
            rows: Optional inclusive, one-based row range for tables.
            columns: Optional zero-based table column indexes to keep.
            aggregate: Optional table operation: ``sum``, ``count``, ``avg``,
                ``min``, or ``max``.
            aggregate_column: Zero-based table column index used by
                ``aggregate``.

        Returns:
            The resource output, or ``None`` when the identifier is absent.

        Raises:
            ValueError: If a plural resource type is supplied.
        """
        resolved_resource_type = ResourceType.parse(resource_type)
        if resolved_resource_type.is_plural:
            raise ValueError("resource_type must be singular, e.g. 'image' not 'images'")
        return render_resource(
            self._require_parsed_presentation(),
            self._package_reader if resolved_resource_type in (ResourceType.IMAGE, ResourceType.MEDIA) else None,
            resolved_resource_type,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )


def open_pptx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> PptxReadSession:
    """Create a context-managed session for repeated PPTX operations.

    Args:
        source: A filesystem path, path-like string, or PPTX bytes.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        A :class:`PptxReadSession`; enter it with ``with`` before reading.
    """
    return PptxReadSession(source, options or ParseOptions())


def parse_pptx(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse a PPTX source and return its LLM-oriented output.

    Args:
        source: A filesystem path, path-like string, or PPTX bytes.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        stream: When true, return an iterator of output chunks.  Parsing still
            completes before the iterator is returned.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        A complete output string, or an iterator when ``stream`` is true.
    """
    output_density = Density.parse(density)
    if stream:
        return iter_slides(source, density=output_density, options=options)
    parse_options = options or ParseOptions()
    parsed_presentation = PptxParser().parse(
        source,
        parse_options if output_density is Density.SEMANTIC else _without_ocr(parse_options),
        plan=PptxParsePlan.render(output_density),
    )
    if output_density is Density.PLAIN:
        return "".join(iter_plain(parsed_presentation))
    if output_density is Density.STRUCTURAL:
        return "".join(iter_structural(parsed_presentation))
    return "".join(iter_semantic(parsed_presentation))


def iter_slides(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    start_slide: int = 1,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Parse a PPTX source and yield one output chunk per selected slide.

    Args:
        source: A filesystem path, path-like string, or PPTX bytes.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        start_slide: One-based first slide to emit.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        An iterator of output chunks.  Parsing completes before iteration
        begins, while chunks remain separated by slide boundaries.

    Raises:
        ValueError: If ``start_slide`` is less than one.
    """
    output_density = Density.parse(density)
    parse_options = options or ParseOptions()
    if isinstance(start_slide, bool) or not isinstance(start_slide, int) or start_slide < 1:
        raise ValueError("start_slide must be greater than zero")
    parsed_presentation = PptxParser().parse(
        source,
        parse_options if output_density is Density.SEMANTIC else _without_ocr(parse_options),
        plan=PptxParsePlan.render(output_density),
    )
    first_slide = True
    selected_slides = parsed_presentation.slides[start_slide - 1 :]
    for slide in selected_slides:
        if output_density is Density.PLAIN:
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
        smartart_nodes = {smartart["id"]: smartart for smartart in parsed_presentation.smartarts}
        slide_output = _render_slide_output(
            slide,
            smartart_nodes,
            semantic=output_density is Density.SEMANTIC,
            ocr_results=parsed_presentation.ocr_results if output_density is Density.SEMANTIC else None,
        )
        if first_slide:
            yield f"density={output_density.value}\n{slide_output}"
            first_slide = False
        else:
            yield slide_output
    if not selected_slides:
        return
    comments_output = _render_comments_output(parsed_presentation)
    if output_density is Density.PLAIN:
        comments_output = _plain_comments_block(parsed_presentation)
    if comments_output and parsed_presentation.comments:
        yield comments_output


def render_window(
    source: str | Path | bytes,
    *,
    slide: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Parse a PPTX source and render a bounded slide window.

    Args:
        source: A filesystem path, path-like string, or PPTX bytes.
        slide: One-based slide number.  ``-1`` selects the last slide.
        span: Number of consecutive slides to include; must be positive.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        Output for the selected slides.

    Raises:
        ValueError: If ``slide`` or ``span`` is invalid.
    """
    output_density = Density.parse(density)
    if isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1:
        raise ValueError("slide must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    parse_options = options or ParseOptions()
    parsed_presentation = PptxParser().parse(
        source,
        _without_ocr(parse_options),
        plan=PptxParsePlan.render(output_density),
    )
    start_index = len(parsed_presentation.slides) + slide if slide < 0 else slide - 1
    start_index = max(0, min(start_index, len(parsed_presentation.slides)))
    selected_presentation = dataclasses.replace(
        parsed_presentation,
        slides=parsed_presentation.slides[start_index : start_index + span],
    )
    if output_density is Density.SEMANTIC:
        _apply_ocr_to_slides(source, selected_presentation, selected_presentation.slides, parse_options)
    if not selected_presentation.slides:
        selected_presentation.comments = []  # empty selection renders as an empty document
    if output_density is Density.PLAIN:
        return "".join(iter_plain(selected_presentation))
    if output_density is Density.STRUCTURAL:
        return "".join(iter_structural(selected_presentation))
    return "".join(iter_semantic(selected_presentation))


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
    """Parse a PPTX source and return one resource by identifier.

    Args:
        source: A filesystem path, path-like string, or PPTX bytes.
        resource_type: Singular resource kind: ``image``, ``media``,
            ``chart``, ``smartart``, or ``table``.
        resource_id: Resource identifier recorded in the presentation.
        rows: Optional inclusive, one-based row range for tables.
        columns: Optional zero-based table column indexes to keep.
        aggregate: Optional table operation: ``sum``, ``count``, ``avg``,
            ``min``, or ``max``.
        aggregate_column: Zero-based table column index used by ``aggregate``.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        The resource output, or ``None`` when the identifier is absent.

    Raises:
        ValueError: If a plural resource type is supplied.
    """
    resolved_resource_type = ResourceType.parse(resource_type)
    if resolved_resource_type.is_plural:
        raise ValueError("resource_type must be singular, e.g. 'image' not 'images'")
    parse_options = options or ParseOptions()
    if resolved_resource_type in (ResourceType.IMAGE, ResourceType.MEDIA, ResourceType.CHART, ResourceType.SMARTART):
        warnings: list[ParseWarning] = []
        with PackageReader(source, _without_ocr(parse_options)) as package_reader:
            package_reader.validate()
            relationships = RelationshipIndex.from_records(package_reader.read_all_relationships())
            if resolved_resource_type in (ResourceType.IMAGE, ResourceType.MEDIA):
                assets, _ = AssetExtractor(package_reader, relationships, warnings).extract()
                parsed_presentation = ParsedPresentation(assets=assets, warnings=warnings)
            else:
                object_extractor = EmbeddedObjectExtractor(package_reader, relationships, warnings)
                if resolved_resource_type is ResourceType.CHART:
                    chart_record = object_extractor.chart_by_id(resource_id)
                    parsed_presentation = ParsedPresentation(
                        charts=[chart_record] if chart_record is not None else [],
                        warnings=warnings,
                    )
                else:
                    smartart_record = object_extractor.smartart_by_id(resource_id)
                    parsed_presentation = ParsedPresentation(
                        smartarts=[smartart_record] if smartart_record is not None else [],
                        warnings=warnings,
                    )
            return render_resource(
                parsed_presentation,
                package_reader,
                resolved_resource_type,
                resource_id,
            )
    if resolved_resource_type is ResourceType.TABLE:
        slide_iterator = PptxParser().iter_slides(source, _without_ocr(parse_options))
        try:
            for _slide, parsed_presentation in slide_iterator:
                if any(
                    shape["type"] == "table" and shape.get("tableId") == resource_id
                    for shape in parsed_presentation.slides[0]["shapes"]
                ):
                    return render_resource(
                        parsed_presentation,
                        None,
                        resolved_resource_type,
                        resource_id,
                        rows=rows,
                        columns=columns,
                        aggregate=aggregate,
                        aggregate_column=aggregate_column,
                    )
            return None
        finally:
            slide_iterator.close()
    parsed_presentation = PptxParser().parse(
        source,
        _without_ocr(parse_options),
        plan=PptxParsePlan.resource(resolved_resource_type),
    )
    return render_resource(
        parsed_presentation,
        None,
        resolved_resource_type,
        resource_id,
        rows=rows,
        columns=columns,
        aggregate=aggregate,
        aggregate_column=aggregate_column,
    )


def _without_ocr(options: ParseOptions) -> ParseOptions:
    return dataclasses.replace(options, ocr=None) if options.ocr is not None else options


def _apply_ocr_to_slides(
    source: str | Path | bytes,
    parsed_presentation: ParsedPresentation,
    selected_slides: list[SlideBlock],
    parse_options: ParseOptions,
) -> None:  # pragma: no cover - OCR provider execution is covered at the adapter boundary
    if parse_options.ocr is None:
        return
    with PackageReader(source, parse_options) as package_reader:
        parsed_presentation.ocr_results = PptxParser._run_ocr(
            package_reader,
            parsed_presentation.assets,
            selected_slides,
            parse_options,
        )
