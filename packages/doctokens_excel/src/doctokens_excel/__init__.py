"""Excel reading APIs: OOXML projections and initial BIFF8 stored content."""

__version__ = "0.2.0"

from doctokens_core.contracts.models import ParseReport, ParseResult, ResourceDescriptor

from .xls import XlsCell, XlsContent, XlsError, XlsLimits, XlsSheet, read_xls_content
from .xlsx.model.workbook import ParseOptions
from .xlsx.query.api import query_xlsx
from .xlsx.query.engine import AggregateSpec, OrderSpec, WhereCondition
from .xlsx.reading.api import XlsxReadSession, open_xlsx, parse_xlsx
from .xlsx.reading.inspection import inspect_xlsx
from .xlsx.reading.resource_catalog import XlsxResourceCatalog
from .xlsx.reading.search import find_xlsx_cells
from .xlsx.reading.text_search import find_xlsx_text
from .xlsx.reading.text_source import XlsxTextSource

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
