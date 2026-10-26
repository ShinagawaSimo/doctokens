"""PPTX parser that produces LLM-readable self-defined output."""

from doctokens_core.contracts.models import ParseReport, ParseResult, ResourceDescriptor

from ._version import __version__
from .pptx.model.presentation import ParseOptions
from .pptx.reading.api import PptxReadSession, open_pptx, parse_pptx

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
