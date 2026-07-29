"""DOCX to LLM-readable structure parser."""

from .concurrency import BatchParseResult, parse_many
from .core.models import ParseOptions, ParsedDocument
from .parser import DocxParser

__all__ = ["BatchParseResult", "DocxParser", "ParseOptions", "ParsedDocument", "parse_many"]
