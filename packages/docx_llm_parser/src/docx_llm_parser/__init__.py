"""DOCX to LLM-readable semantic HTML5 parser."""

from ._version import __version__
from .api import get_resource, parse_docx, render_window, write_document
from .core.enums import Density, ResourceType

__all__ = [
    "Density",
    "ResourceType",
    "__version__",
    "get_resource",
    "parse_docx",
    "render_window",
    "write_document",
]
