"""PPTX parser that produces LLM-readable self-defined output."""

from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor

from ._version import __version__
from .api import PptxReadSession, open_pptx, parse_pptx
from .core.models import ParseOptions

__all__ = [
    "ParseOptions",
    "ParseReport",
    "ParseResult",
    "PptxReadSession",
    "ResourceDescriptor",
    "__version__",
    "open_pptx",
    "parse_pptx",
]
