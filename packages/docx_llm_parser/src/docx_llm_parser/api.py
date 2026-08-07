"""Public API — accepts source files directly, returns rendered/extracted results."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .core.enums import Density, ResourceType
from .core.models import ParseOptions, ResourceDetail
from .parser import DocxParser
from .renderers.html5 import extract as _extract_resources
from .renderers.html5 import iter_html5 as _iter_html5
from .renderers.html5 import to_html5 as _to_html5
from .renderers.html5 import window as _window
from .renderers.html5 import write_outputs


def render_document(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Parse *source* and render to the requested text density."""
    parsed = DocxParser().parse(source, options)
    return _to_html5(parsed, density)


def iter_document(
    source: str | Path | bytes,
    *,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> Iterator[str]:
    """Stream rendered chunks from *source* without building the full string."""
    parsed = DocxParser().parse(source, options)
    yield from _iter_html5(parsed, density)


def write_document(
    source: str | Path | bytes,
    output_dir: str | Path,
    *,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> Path:
    """Parse *source* and write the rendered file to *output_dir*."""
    parsed = DocxParser().parse(source, options)
    paths = write_outputs(parsed, Path(output_dir), density)
    return Path(paths["html"])


def render_window(
    source: str | Path | bytes,
    *,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
    options: ParseOptions | None = None,
) -> str:
    """Render a page range from *source*; ``page=-1`` selects the last page."""
    parsed = DocxParser().parse(source, options)
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
) -> ResourceDetail | None:
    """Extract one resource by ID from *source*.

    ``rows`` is a range string like ``"10-25"`` (inclusive, 1-based).
    ``columns`` filters by header name.
    ``aggregate`` is one of ``sum``, ``count``, ``avg``, ``min``, ``max`` and
    requires ``aggregate_column``.
    """
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural:
        raise ValueError("resource_type must be singular when getting one resource")
    parsed = DocxParser().parse(source, options)
    items = _extract_resources(
        parsed, resolved_type, resource_id,
        rows=rows, columns=columns,
        aggregate=aggregate, aggregate_column=aggregate_column,
    )
    return items[0] if items else None
