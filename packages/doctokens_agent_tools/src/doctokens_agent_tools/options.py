"""Translate reviewed tool options into immutable format options."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docx_llm_parser import ParseOptions as DocxOptions
from pptx_llm_parser import ParseOptions as PptxOptions
from xlsx_llm_parser import ParseOptions as XlsxOptions

from .config import RuntimeConfig
from .models import ToolError
from .schemas import DocumentOptions


def parser_options(format_name: str, options: DocumentOptions, config: RuntimeConfig) -> DocxOptions | PptxOptions | XlsxOptions:
    values: dict[str, Any] = asdict(config.package_options)
    selected = options.model_dump(exclude_none=True)
    enabled = selected.pop("enable_ocr")
    docx_keys = {"revision_mode", "preserve_empty_paragraphs", "include_runs", "include_raw_hints"}
    allowed = docx_keys if format_name == "docx" else {"locale"} if format_name == "xlsx" else set()
    if set(selected) - allowed:
        raise ToolError("INVALID_ARGUMENT", f"options {sorted(set(selected) - allowed)} are not supported for {format_name}")
    values.update(selected)
    if enabled:
        if format_name == "xlsx" or config.ocr_provider is None:
            raise ToolError("OCR_UNAVAILABLE", "OCR requires a host-configured provider and a DOCX/PPTX document")
        values.update(ocr=config.ocr_provider, ocr_workers=config.ocr_workers, ocr_timeout=config.ocr_timeout)
    if format_name == "docx":
        return DocxOptions(**values)
    if format_name == "pptx":
        return PptxOptions(**values)
    return XlsxOptions(**values)
