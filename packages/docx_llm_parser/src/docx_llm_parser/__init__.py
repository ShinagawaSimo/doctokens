"""DOCX to LLM-readable semantic HTML5 parser."""

from ooxml_llm_core.models import ParseReport

from ._version import __version__
from .api import LoadedDocx, get_resource, load_docx, parse_docx, render_window
from .core.enums import Density, ResourceType
from .core.models import ParseOptions
from .plan import DocxFeature, DocxParsePlan

__all__ = [
    "Density",
    "DocxFeature",
    "DocxParsePlan",
    "LoadedDocx",
    "ParseOptions",
    "ParseReport",
    "ResourceType",
    "__version__",
    "get_resource",
    "load_docx",
    "parse_docx",
    "render_window",
]
