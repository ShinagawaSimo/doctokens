"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.1.0"

from xlsx_llm_parser.api import (
    find_cells,
    get_resource,
    iter_workbook,
    parse_xlsx,
    query_data,
    render_range,
)

__all__ = [
    "find_cells",
    "get_resource",
    "iter_workbook",
    "parse_xlsx",
    "query_data",
    "render_range",
]
