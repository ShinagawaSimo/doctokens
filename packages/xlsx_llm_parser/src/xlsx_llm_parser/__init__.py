"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.1.0"

from ooxml_llm_core.models import ParseReport

from xlsx_llm_parser.api import (
    LoadedWorkbook,
    find_cells,
    get_resource,
    iter_workbook,
    load_xlsx,
    parse_xlsx,
    query_data,
    render_range,
)
from xlsx_llm_parser.models import ParseOptions

__all__ = [
    "LoadedWorkbook",
    "ParseOptions",
    "ParseReport",
    "find_cells",
    "get_resource",
    "iter_workbook",
    "load_xlsx",
    "parse_xlsx",
    "query_data",
    "render_range",
]
