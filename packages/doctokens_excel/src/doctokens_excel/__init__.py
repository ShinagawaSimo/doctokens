"""Excel reading APIs: OOXML projections and initial BIFF8 stored content."""

__version__ = "0.2.0"

from doctokens_core.models import ParseReport, ParseResult, ResourceDescriptor

from doctokens_excel.api import XlsxReadSession, open_xlsx, parse_xlsx
from doctokens_excel.data_query import query_xlsx
from doctokens_excel.inspection import inspect_xlsx
from doctokens_excel.models import ParseOptions
from doctokens_excel.query import AggregateSpec, OrderSpec, WhereCondition
from doctokens_excel.resource_catalog import XlsxResourceCatalog
from doctokens_excel.search import find_xlsx_cells
from doctokens_excel.text_search import find_xlsx_text
from doctokens_excel.text_source import XlsxTextSource
from doctokens_excel.xls import XlsCell, XlsContent, XlsError, XlsLimits, XlsSheet, read_xls_content

__all__ = [
    "AggregateSpec",
    "OrderSpec",
    "ParseOptions",
    "ParseReport",
    "ParseResult",
    "ResourceDescriptor",
    "WhereCondition",
    "XlsCell",
    "XlsContent",
    "XlsError",
    "XlsLimits",
    "XlsSheet",
    "XlsxReadSession",
    "XlsxResourceCatalog",
    "XlsxTextSource",
    "find_xlsx_cells",
    "find_xlsx_text",
    "inspect_xlsx",
    "open_xlsx",
    "parse_xlsx",
    "query_xlsx",
    "read_xls_content",
]
