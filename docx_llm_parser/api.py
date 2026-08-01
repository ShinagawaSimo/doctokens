"""面向库调用的公共 API 辅助函数。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .core.enums import Density, ResourceType
from .core.models import (
    DocumentManifest,
    ParsedDocument,
    ParseOptions,
    ResourceDetail,
    ResourceSummary,
)
from .parser import DocxParser
from .renderers.html5 import extract as _extract_resources
from .renderers.html5 import iter_html5 as _iter_html5
from .renderers.html5 import manifest as _manifest
from .renderers.html5 import to_html5 as _to_html5
from .renderers.html5 import window as _window
from .renderers.html5 import write_outputs


def parse_docx(docx_path: str | Path, options: ParseOptions | None = None) -> ParsedDocument:
    """解析单个 DOCX 文件，返回结构化文档模型。"""
    return DocxParser().parse(docx_path, options)


def render_document(
    document: ParsedDocument,
    *,
    density: Density | str = Density.SEMANTIC,
) -> str:
    """Render a parsed document to the requested text density."""
    return _to_html5(document, density)


def iter_document(
    document: ParsedDocument,
    *,
    density: Density | str = Density.SEMANTIC,
) -> Iterator[str]:
    """Stream rendered document chunks without building the whole string first."""
    yield from _iter_html5(document, density)


def write_document(
    document: ParsedDocument,
    output_dir: str | Path,
    *,
    density: Density | str = Density.SEMANTIC,
) -> Path:
    """Write a rendered document file and return the replaced target path."""
    paths = write_outputs(document, Path(output_dir), density)
    return Path(paths["html"])


def render_window(
    document: ParsedDocument,
    *,
    page: int,
    span: int = 1,
    density: Density | str = Density.SEMANTIC,
) -> str:
    """Render a page range; `page=-1` selects the last page."""
    return _window(document, page, span, density)


def build_manifest(document: ParsedDocument) -> DocumentManifest:
    """Return a compact document overview for planning reads."""
    return _manifest(document)


def list_resources(
    document: ParsedDocument,
    resource_type: ResourceType | str,
) -> tuple[ResourceSummary, ...]:
    """Return summaries for a plural resource type such as images, charts, or tables."""
    resolved_type = ResourceType.parse(resource_type)
    if not resolved_type.is_plural:
        raise ValueError("resource_type must be plural when listing resources")
    return tuple(_extract_resources(document, resolved_type))


def get_resource(
    document: ParsedDocument,
    resource_type: ResourceType | str,
    resource_id: str,
) -> ResourceDetail | None:
    """Return one resource detail by ID, or None when the ID is absent."""
    resolved_type = ResourceType.parse(resource_type)
    if resolved_type.is_plural:
        raise ValueError("resource_type must be singular when getting one resource")
    items = _extract_resources(document, resolved_type, resource_id)
    return items[0] if items else None
