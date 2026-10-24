"""Host-owned full-session admission, reservations and inactive-session eviction."""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from docx_llm_parser import ParseOptions as DocxOptions
from docx_llm_parser import open_docx
from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.memory import ParseMemoryLimitError, estimate_session_bytes
from ooxml_llm_core.package import PackageReader
from pptx_llm_parser import ParseOptions as PptxOptions
from pptx_llm_parser import open_pptx
from xlsx_llm_parser import open_xlsx

from .config import RuntimeConfig
from .models import ToolError

if TYPE_CHECKING:
    from .documents import Document, Session


def session_bytes(documents: Collection[Document]) -> int:
    return sum(d.session_memory_bytes for d in documents)


def _reservation(document: Document) -> int:
    if document.session_reservation is None:
        options = document.options
        limits = PackageLimits(
            options.max_zip_entries, options.max_entry_uncompressed_bytes, options.max_total_uncompressed_bytes
        )
        with PackageReader(document.snapshot, limits) as package:
            required = {"docx": "word/document.xml", "pptx": "ppt/presentation.xml", "xlsx": "xl/workbook.xml"}
            package.validate(required[document.format])
            document.session_reservation = estimate_session_bytes(package.read_entry_index())
    return document.session_reservation


def _open(document: Document, allowance: int) -> Session:
    options = document.options
    if isinstance(options, DocxOptions):
        return open_docx(document.snapshot, options=options, memory_limit_bytes=allowance)
    if isinstance(options, PptxOptions):
        return open_pptx(document.snapshot, options=options, memory_limit_bytes=allowance)
    return open_xlsx(document.snapshot, options=options, memory_limit_bytes=allowance)


def _memory_error() -> ToolError:
    return ToolError(
        "SESSION_MEMORY_LIMIT",
        "complete session exceeds the estimated-memory budget; use bounded XLSX reads/search/query, "
        "or increase the host session memory limits",
    )


def admit_session(document: Document, documents: Collection[Document], config: RuntimeConfig) -> Session:
    required = _reservation(document)
    maximum = min(config.max_session_memory_bytes, config.max_session_total_memory_bytes)
    if required > maximum:
        raise _memory_error()
    sessions = [d for d in documents if d.session is not None]
    candidates = sorted((d for d in sessions if not d.active), key=lambda d: d.session_touched)
    while len(sessions) >= config.max_sessions or session_bytes(documents) + required > config.max_session_total_memory_bytes:
        if not candidates:
            if len(sessions) >= config.max_sessions:
                raise ToolError("CAPACITY_EXCEEDED", "all cached sessions are in use")
            raise _memory_error()
        victim = candidates.pop(0)
        victim.close_session()
        sessions.remove(victim)
    while True:
        allowance = min(maximum, config.max_session_total_memory_bytes - session_bytes(documents))
        opened = _open(document, allowance)
        try:
            opened.__enter__()
            estimated = max(required, opened.estimated_memory_bytes)
        except ParseMemoryLimitError as exc:
            opened.close()
            # Growth can exceed the source-size reservation. Reclaim remaining
            # idle owners before one retry with the largest available allowance.
            if candidates and allowance < maximum:
                for victim in candidates:
                    victim.close_session()
                candidates.clear()
                continue
            raise _memory_error() from exc
        except BaseException:
            opened.close()
            raise
        document.session_memory_bytes = estimated
        document.session = opened
        return opened
