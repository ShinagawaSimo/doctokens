"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.1.0"

from xlsx_llm_parser.parser import parse_xlsx
from xlsx_llm_parser.renderers.structural import (
    Density,
    iter_workbook,
    render_range,
    render_workbook,
)

__all__ = ["parse_xlsx", "render_workbook", "iter_workbook", "render_range", "Density"]

