"""Public API — accepts source files directly, returns rendered/extracted results."""

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
from .renderers.html5 import iter_html5 as _iter_html5
from .renderers.html5 import render_resource as _render_resource
from .renderers.html5 import to_html5 as _to_html5
from .renderers.html5 import window as _window


class LoadedDocx:
    """Explicitly loaded DOCX facade for repeated downstream operations."""

    def __init__(self, parsed: ParsedDocument, options: ParseOptions) -> None:
        self.parsed = parsed
        self.options = options

    @property
    def report(self) -> ParseReport:
        if self.parsed.report is None:  # pragma: no cover - parser always attaches reports
            raise RuntimeError("parsed DOCX has no parse report")
        return self.parsed.report

    def render(self, *, density: Density | str = Density.SEMANTIC) -> str:
        return _to_html5(self.parsed, density)

    def iter_render(self, *, density: Density | str = Density.SEMANTIC) -> Iterator[str]:
        return _iter_html5(self.parsed, density)

    def render_window(
        self,
        *,
        page: int,
        span: int = 1,
        density: Density | str = Density.SEMANTIC,
    ) -> str:
        return _window(self.parsed, page, span, density)

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
        resolved_type = ResourceType.parse(resource_type)
        if resolved_type.is_plural:
            raise ValueError("resource_type must be singular when getting one resource")
        items = _render_resource(
            self.parsed,
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
    """Parse *source* and render to the requested text density.

    Returns a string by default.  Set *stream=True* to receive an iterator
    of rendered output chunks. Parsing itself is still completed first.
    """
    opts = options or ParseOptions()
    parsed = DocxParser().parse(source, opts, plan=DocxParsePlan.render(density))
    if stream:
        return _iter_html5(parsed, density)
    return _to_html5(parsed, density)


def load_docx(source: str | Path | bytes, *, options: ParseOptions | None = None) -> LoadedDocx:
    """Parse once and return an explicit reusable DOCX facade."""
    opts = options or ParseOptions()
    return LoadedDocx(DocxParser().parse(source, opts, plan=DocxParsePlan.session()), opts)


def render_window(
    source: str | Path | bytes,
    *,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Render a page range from *source*; ``page=-1`` selects the last page."""
    opts = options or ParseOptions()
    parsed = DocxParser().parse(source, opts, plan=DocxParsePlan.render(density))
    return _window(parsed, page, span, density)


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
    """Extract one resource by ID from *source* as an HTML string.

    ``rows`` is a range string like ``"10-25"`` (inclusive, 1-based).
    ``columns`` filters by header name.
    ``aggregate`` is one of ``sum``, ``count``, ``avg``, ``min``, ``max`` and
    requires ``aggregate_column``.
    """
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural:
        raise ValueError("resource_type must be singular when getting one resource")
    opts = options or ParseOptions()
    if opts.ocr is None:
        parsed = DocxParser().parse(source, opts, plan=DocxParsePlan.resource(resolved_type))
        items = _render_resource(
            parsed,
            resolved_type,
            resource_id,
            rows=rows,
            columns=columns,
            aggregate=aggregate,
            aggregate_column=aggregate_column,
        )
        return items[0] if items else None
    parsed = DocxParser().parse(source, dataclasses.replace(opts, ocr=None), plan=DocxParsePlan.resource(resolved_type))
    if resolved_type is ResourceType.IMAGE and opts.ocr is not None:
        asset = next((item for item in parsed.assets if item["id"] == resource_id), None)
        if asset is not None:
            with PackageReader(source, opts) as package:
                parsed.ocr_results = DocxParser._run_ocr(package, [asset], opts)
    items = _render_resource(
        parsed,
        resolved_type,
        resource_id,
        rows=rows,
        columns=columns,
        aggregate=aggregate,
        aggregate_column=aggregate_column,
    )
    return items[0] if items else None
