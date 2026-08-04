"""DOCX 到 LLM 可读结构的解析库。"""

from ._version import __version__
from .api import (
    build_manifest,
    get_resource,
    iter_document,
    list_resources,
    parse_docx,
    render_document,
    render_window,
)
from .core.enums import Density, ResourceType, RevisionMode
from .core.models import ParsedDocument, ParseOptions, ParseWarning
from .parser import DocxParser

__all__ = [
    "Density",
    "DocxParser",
    "ParseOptions",
    "ParseWarning",
    "ParsedDocument",
    "ResourceType",
    "RevisionMode",
    "__version__",
    "build_manifest",
    "get_resource",
    "iter_document",
    "list_resources",
    "parse_docx",
    "render_document",
    "render_window",
]
