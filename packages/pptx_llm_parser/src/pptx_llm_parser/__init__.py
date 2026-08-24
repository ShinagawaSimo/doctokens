"""PPTX to LLM-readable semantic HTML5 parser."""

from ooxml_llm_core.models import ParseReport

from ._version import __version__
from .api import PptxReadSession, get_resource, iter_slides, open_pptx, parse_pptx, render_window
from .core.enums import Density, ResourceType
from .core.models import ParseOptions

__all__ = [
    "Density",
    "ParseOptions",
    "ParseReport",
    "PptxReadSession",
    "ResourceType",
    "__version__",
    "get_resource",
    "iter_slides",
    "open_pptx",
    "parse_pptx",
    "render_window",
]
