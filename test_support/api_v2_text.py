"""Test-only text views over the v2 parser APIs.

Existing rendering tests assert markup details rather than public return
types.  Keeping that intent in one adapter lets the production packages drop
their old text-returning convenience functions.
"""

from __future__ import annotations

from typing import Any

from docx_llm_parser import open_docx
from docx_llm_parser import parse_docx as _parse_docx
from pptx_llm_parser import open_pptx
from pptx_llm_parser import parse_pptx as _parse_pptx
from xlsx_llm_parser import open_xlsx
from xlsx_llm_parser import parse_xlsx as _parse_xlsx


class Density:
    PLAIN = "plain"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"

    def __new__(cls, value: str) -> str:
        if value not in {cls.PLAIN, cls.STRUCTURAL, cls.SEMANTIC}:
            raise ValueError(value)
        return value


def parse_docx(source: object, **kwargs: Any) -> str:
    return _parse_docx(source, **kwargs).text


def render_docx_window(source: object, *, page: int, span: int = 1, **kwargs: Any) -> str:
    return _parse_docx(source, page_hint=page, span=span, **kwargs).text


def parse_pptx(source: object, **kwargs: Any) -> str:
    return _parse_pptx(source, **kwargs).text


def render_pptx_window(source: object, *, slide: int, span: int = 1, **kwargs: Any) -> str:
    return _parse_pptx(source, slide=slide, span=span, **kwargs).text


def parse_xlsx(source: object, **kwargs: Any) -> str:
    return _parse_xlsx(source, **kwargs).text


def render_xlsx_range(source: object, sheet: str, range_spec: str, **kwargs: Any) -> str:
    return _parse_xlsx(source, sheet=sheet, range_spec=range_spec, **kwargs).text


def find_xlsx_cells(source: object, query: str, **kwargs: Any) -> str:
    with open_xlsx(source) as workbook:
        return workbook.find_cells(query, **kwargs).text


def query_xlsx_data(source: object, **kwargs: Any) -> str:
    with open_xlsx(source) as workbook:
        return workbook.query_data(**kwargs).text


def render_docx_resource(source: object, kind: str, resource_id: str, **kwargs: Any) -> str:
    with open_docx(source) as document:
        return document.render_resource(kind, resource_id, **kwargs).text


def render_pptx_resource(source: object, kind: str, resource_id: str, **kwargs: Any) -> str:
    with open_pptx(source) as presentation:
        return presentation.render_resource(kind, resource_id, **kwargs).text


__all__ = [
    "Density",
    "find_xlsx_cells",
    "parse_docx",
    "parse_pptx",
    "parse_xlsx",
    "query_xlsx_data",
    "render_docx_resource",
    "render_docx_window",
    "render_pptx_resource",
    "render_pptx_window",
    "render_xlsx_range",
]
