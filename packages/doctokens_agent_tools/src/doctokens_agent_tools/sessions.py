"""Host-owned full-session admission, reservations and inactive-session eviction."""

from __future__ import annotations

from _thread import RLock
from collections.abc import Collection
from typing import TYPE_CHECKING

from docx_llm_parser import ParseOptions as DocxOptions
from docx_llm_parser import open_docx
from ooxml_llm_core.execution import checkpoint
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


def admit_session(
    document: Document, documents: Collection[Document], config: RuntimeConfig, lock: RLock | None = None
) -> Session:
    gate = lock or RLock()
    required = _reservation(document)
    maximum = min(config.max_session_memory_bytes, config.max_session_total_memory_bytes)
    if required > maximum:
        raise _memory_error()
    for attempt in range(2):
        with gate:
            checkpoint("admitting parser session")
            sessions = [d for d in documents if d.session is not None or d.session_loading]
            candidates = sorted((d for d in sessions if not d.active and not d.session_loading), key=lambda d: d.session_touched)
            while (
                len(sessions) >= config.max_sessions
                or session_bytes(documents) + required > config.max_session_total_memory_bytes
            ):
                if not candidates:
                    if len(sessions) >= config.max_sessions:
                        raise ToolError("CAPACITY_EXCEEDED", "all cached sessions are in use")
                    raise _memory_error()
                victim = candidates.pop(0)
                victim.close_session()
                sessions.remove(victim)
            allowance = min(maximum, config.max_session_total_memory_bytes - session_bytes(documents))
            # Reserve growth capacity before leaving the lock, so two concurrent
            # parses cannot both spend the same aggregate allowance.
            document.session_memory_bytes = allowance
            document.session_loading = True
        opened: Session | None = None
        try:
            opened = _open(document, allowance)
            opened.__enter__()
            estimated = max(required, opened.estimated_memory_bytes)
            if estimated > allowance:
                raise ParseMemoryLimitError("session growth exceeds reserved capacity")
            checkpoint("parser session ready")
        except BaseException as exc:
            if opened is not None:
                opened.close()
            with gate:
                document.session_memory_bytes = 0
                document.session_loading = False
                retry = isinstance(exc, ParseMemoryLimitError) and attempt == 0 and allowance < maximum
                victims = sorted(
                    (d for d in documents if (d.session is not None or d.session_loading) and not d.active and d is not document),
                    key=lambda d: d.session_touched,
                )
                if retry and victims:
                    for victim in victims:
                        victim.close_session()
                else:
                    retry = False
            if retry:
                continue
            if isinstance(exc, ParseMemoryLimitError):
                raise _memory_error() from exc
            raise
        with gate:
            document.session = opened
            document.session_memory_bytes = estimated
            document.session_loading = False
        return opened
    raise AssertionError("unreachable admission retry")
