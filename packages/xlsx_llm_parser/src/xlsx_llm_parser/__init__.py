"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.1.0"

from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor

from xlsx_llm_parser.api import XlsxReadSession, open_xlsx, parse_xlsx
from xlsx_llm_parser.models import ParseOptions

__all__ = [
    "ParseOptions",
    "ParseReport",
    "ParseResult",
    "ResourceDescriptor",
    "XlsxReadSession",
    "open_xlsx",
    "parse_xlsx",
]
