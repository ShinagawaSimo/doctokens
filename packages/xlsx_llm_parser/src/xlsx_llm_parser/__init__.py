"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.2.0"

from ooxml_llm_core.models import ParseReport, ParseResult, ResourceDescriptor

from xlsx_llm_parser.api import XlsxReadSession, open_xlsx, parse_xlsx
from xlsx_llm_parser.data_query import query_xlsx
from xlsx_llm_parser.inspection import inspect_xlsx
from xlsx_llm_parser.models import ParseOptions
from xlsx_llm_parser.query import AggregateSpec, OrderSpec, WhereCondition
from xlsx_llm_parser.resource_catalog import XlsxResourceCatalog
from xlsx_llm_parser.search import find_xlsx_cells
from xlsx_llm_parser.text_search import find_xlsx_text

__all__ = [
    "AggregateSpec",
    "OrderSpec",
    "ParseOptions",
    "ParseReport",
    "ParseResult",
    "ResourceDescriptor",
    "WhereCondition",
    "XlsxReadSession",
    "XlsxResourceCatalog",
    "find_xlsx_cells",
    "find_xlsx_text",
    "inspect_xlsx",
    "open_xlsx",
    "parse_xlsx",
    "query_xlsx",
]
