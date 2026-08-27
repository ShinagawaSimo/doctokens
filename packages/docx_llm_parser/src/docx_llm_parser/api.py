"""Public DOCX API for parsing, rendering, and resource extraction."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

from ooxml_llm_core.models import ParseReport

from .core.enums import Density, ResourceType
from .core.models import ParsedDocument, ParseOptions
from .core.package import PackageReader
from .parser import DocxParser
from .plan import DocxParsePlan
from .renderers.output import iter_output as _iter_output
from .renderers.output import render_page_window as _render_page_window
from .renderers.output import render_resource as _render_resource
from .renderers.output import to_output as _to_output


class LoadedDocx:
    """Reusable, already-parsed DOCX document facade.

    The document is parsed once by :func:`load_docx`.  The facade then supports
    repeated output rendering and resource reads without reopening the source
    document.  It owns the parsed in-memory representation, but it does not
    cache application-level queries or coordinate downstream work.
    """

    def __init__(self, parsed_document: ParsedDocument, parse_options: ParseOptions) -> None:
        self.parsed_document = parsed_document
        self.parse_options = parse_options

    @property
    def report(self) -> ParseReport:
        """Return diagnostics collected while parsing this document."""
        if self.parsed_document.report is None:  # pragma: no cover - parser always attaches reports
            raise RuntimeError("parsed DOCX has no parse report")
        return self.parsed_document.report

    def render(self, *, density: Density | str = Density.SEMANTIC) -> str:
        """Render the complete document at the requested text density.

        Args:
            density: ``plain`` for text only, ``structural`` for document
                structure, or ``semantic`` for structure plus formatting and
                content details.  A :class:`Density` value may be supplied.

        Returns:
            The complete self-defined LLM output string.
        """
        return _to_output(self.parsed_document, density)

    def iter_render(self, *, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
        """Yield complete-document output chunks at the requested density.

        Args:
            density: Output detail level.  Parsing has already completed; the
                iterator controls output iteration only.

        Returns:
            An iterator whose chunks concatenate to the same value as
            :meth:`render`.
        """
        return _iter_output(self.parsed_document, density)

    def render_window(
        self,
        *,
        page: int,
        span: int = 1,
        density: Density | str = Density.SEMANTIC,
    ) -> str:
        """Render a bounded page window from the loaded document.

        Args:
            page: One-based page number.  ``-1`` selects the last page.
            span: Number of consecutive pages to include; must be positive.
            density: Output detail level.

        Returns:
            Output for the selected pages.  Missing pages produce an empty
            selection rather than falling back to the whole document.

        Raises:
            ValueError: If ``page`` or ``span`` is invalid.
        """
        return _render_page_window(self.parsed_document, page, span, density)

    def get_resource(
        self,
        resource_type: ResourceType | str,
        resource_id: str,
        *,
        rows: str | None = None,
        columns: list[str] | None = None,
        aggregate: str | None = None,
        aggregate_column: str | None = None,
    ) -> str | None:
        """Return one resource from the loaded document.

        Args:
            resource_type: Singular resource kind, such as ``image``,
                ``chart``, ``smartart``, or ``table``.
            resource_id: Resource identifier recorded in the parsed document.
            rows: Optional inclusive, one-based row range such as ``10-25``
                for table resources.
            columns: Optional table header names to keep.
            aggregate: Optional table operation: ``sum``, ``count``, ``avg``,
                ``min``, or ``max``.
            aggregate_column: Header name used by ``aggregate``.

        Returns:
            The resource output, or ``None`` when the identifier is absent.

        Raises:
            ValueError: If a plural resource type is supplied.
        """
        resolved_type = ResourceType.parse(resource_type)
        if resolved_type.is_plural:
            raise ValueError("resource_type must be singular when getting one resource")
        items = _render_resource(
            self.parsed_document,
            resolved_type,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
        return items[0] if items else None


def parse_docx(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    stream: bool = False,
    options: ParseOptions | None = None,
) -> str | Iterator[str]:
    """Parse a DOCX source and return its LLM-oriented output.

    Args:
        source: A filesystem path, path-like string, or DOCX bytes.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        stream: When true, return an iterator of output chunks.  Parsing is
            still completed before the iterator is returned; this flag affects
            output iteration only.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        A complete output string by default, or an iterator when ``stream`` is
        true.
    """
    parse_options = options or ParseOptions()
    parsed_document = DocxParser().parse(
        source,
        parse_options,
        plan=DocxParsePlan.render(density),
    )
    if stream:
        return _iter_output(parsed_document, density)
    return _to_output(parsed_document, density)


def load_docx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> LoadedDocx:
    """Parse a DOCX source once and return a reusable document facade.

    Args:
        source: A filesystem path, path-like string, or DOCX bytes.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        A :class:`LoadedDocx` that can render output and read resources
        repeatedly from the parsed representation.
    """
    parse_options = options or ParseOptions()
    parsed_document = DocxParser().parse(source, parse_options, plan=DocxParsePlan.session())
    return LoadedDocx(parsed_document, parse_options)


def render_window(
    source: str | Path | bytes,
    *,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Parse a DOCX source and render a bounded page window.

    Args:
        source: A filesystem path, path-like string, or DOCX bytes.
        page: One-based page number.  ``-1`` selects the last page.
        span: Number of consecutive pages to include; must be positive.
        density: ``plain``, ``structural``, or ``semantic`` output detail.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        Output for the selected pages.

    Raises:
        ValueError: If ``page`` or ``span`` is invalid.
    """
    parse_options = options or ParseOptions()
    parsed_document = DocxParser().parse(
        source,
        parse_options,
        plan=DocxParsePlan.render(density),
    )
    return _render_page_window(parsed_document, page, span, density)


def get_resource(
    source: str | Path | bytes,
    resource_type: ResourceType | str,
    resource_id: str,
    *,
    rows: str | None = None,
    columns: list[str] | None = None,
    aggregate: str | None = None,
    aggregate_column: str | None = None,
    options: ParseOptions | None = None,
) -> str | None:
    """Parse a DOCX source and return one resource by identifier.

    Args:
        source: A filesystem path, path-like string, or DOCX bytes.
        resource_type: Singular resource kind, such as ``image``, ``chart``,
            ``smartart``, or ``table``.
        resource_id: Resource identifier recorded in the parsed document.
        rows: Optional inclusive, one-based row range such as ``10-25``.
        columns: Optional table header names to keep.
        aggregate: Optional table operation: ``sum``, ``count``, ``avg``,
            ``min``, or ``max``.
        aggregate_column: Header name used by ``aggregate``.
        options: Optional parser limits, feature, and OCR configuration.

    Returns:
        The resource output, or ``None`` when the identifier is absent.

    Raises:
        ValueError: If a plural resource type is supplied.
    """
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural:
        raise ValueError("resource_type must be singular when getting one resource")
    parse_options = options or ParseOptions()
    if parse_options.ocr is None:
        parsed_document = DocxParser().parse(
            source,
            parse_options,
            plan=DocxParsePlan.resource(resolved_type),
        )
        items = _render_resource(
            parsed_document,
            resolved_type,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
        return items[0] if items else None
    parsed_document = DocxParser().parse(
        source,
        dataclasses.replace(parse_options, ocr=None),
        plan=DocxParsePlan.resource(resolved_type),
    )
    if resolved_type is ResourceType.IMAGE and parse_options.ocr is not None:
        asset = next((item for item in parsed_document.assets if item["id"] == resource_id), None)
        if asset is not None:
            with PackageReader(source, parse_options) as package:
                parsed_document.ocr_results = DocxParser._run_ocr(package, [asset], parse_options)
    items = _render_resource(
        parsed_document,
        resolved_type,
        resource_id,
        rows=rows,
        columns=columns,
        aggregate=aggregate,
        aggregate_column=aggregate_column,
    )
    return items[0] if items else None
