"""DOCX to LLM-readable semantic HTML5 parser."""

from ._version import __version__
from .api import get_resource, iter_document, render_document, render_window, write_document
from .core.enums import Density, ResourceType

__all__ = [
    "Density",
    "ResourceType",
    "__version__",
    "get_resource",
    "iter_document",
    "render_document",
    "render_window",
    "write_document",
]
