"""DOCX parser that produces LLM-readable self-defined output."""

from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor

from ._version import __version__
from .api import DocxReadSession, open_docx, parse_docx
from .core.models import ParseOptions

__all__ = [
    "DocxReadSession",
    "ParseOptions",
    "ParseReport",
    "ParseResult",
    "ResourceDescriptor",
    "__version__",
    "open_docx",
    "parse_docx",
]
