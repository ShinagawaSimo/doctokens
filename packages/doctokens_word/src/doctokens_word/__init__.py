"""DOCX parser that produces LLM-readable self-defined output."""

from doctokens_core.contracts.models import ParseReport, ParseResult, ResourceDescriptor

from ._version import __version__
from .docx.model import ParseOptions
from .docx.reading.api import DocxReadSession, open_docx, parse_docx

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
