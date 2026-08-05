"""XLSX LLM Parser — convert Excel workbooks to LLM-readable semantic markup."""

__version__ = "0.1.0"

from xlsx_llm_parser.api import iter_workbook, render_range, render_workbook
from xlsx_llm_parser.parser import parse_xlsx

__all__ = ["parse_xlsx", "render_workbook", "iter_workbook", "render_range"]
