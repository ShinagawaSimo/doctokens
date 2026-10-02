"""Versioned local snapshots and bounded ownership of parser sessions."""

from __future__ import annotations

import hashlib
import tempfile
import time
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from docx_llm_parser import DocxReadSession, open_docx
from docx_llm_parser import ParseOptions as DocxOptions
from pptx_llm_parser import ParseOptions as PptxOptions
from pptx_llm_parser import PptxReadSession, open_pptx
from xlsx_llm_parser import ParseOptions as XlsxOptions
from xlsx_llm_parser import XlsxReadSession, open_xlsx

from .config import RuntimeConfig
from .models import ToolError
from .options import parser_options
from .schemas import DocumentOptions, SourceArgs

Session = DocxReadSession | PptxReadSession | XlsxReadSession
Options = DocxOptions | PptxOptions | XlsxOptions


@dataclass
class Document:
    id: str
    original: Path
    snapshot: Path
    revision: str
    fingerprint: tuple[int, int, int]
    options_key: str
    options: Options
    size: int
    touched: float
    session: Session | None = None
    session_touched: float = 0
    active: int = 0

    @property
    def format(self) -> str:
        return self.original.suffix.lower()[1:]

    def close_session(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None


class DocumentStore:
    """Called under the runtime lock; leases protect active snapshots."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.directory = tempfile.TemporaryDirectory(prefix="doctokens-tools-")
        self.documents: OrderedDict[str, Document] = OrderedDict()
        self.bytes = 0

    def path(self, value: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.config.allowed_roots[0] / candidate
        resolved = candidate.resolve()
        if not any(resolved.is_relative_to(root) for root in self.config.allowed_roots):
            raise ToolError("PATH_NOT_ALLOWED", "file is outside the configured allowed roots")
        if not resolved.is_file():
            raise ToolError("DOCUMENT_NOT_FOUND", "file does not exist or is not a regular file")
        if resolved.suffix.lower() not in {".docx", ".pptx", ".xlsx"}:
            raise ToolError("UNSUPPORTED_FORMAT", "supported file extensions are .docx, .pptx and .xlsx")
        return resolved

    @staticmethod
    def fingerprint(path: Path) -> tuple[int, int, int]:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def expire(self) -> list[str]:
        now = time.monotonic()
        removed = []
        for document in list(self.documents.values()):
            if document.active:
                continue
            if now - document.touched >= self.config.idle_seconds:
                removed.append(document.id)
                self.remove(document.id)
            elif document.session is not None and now - document.session_touched >= self.config.idle_seconds:
                document.close_session()
        return removed

    def remove(self, identifier: str) -> None:
        document = self.documents.pop(identifier)
        document.close_session()
        document.snapshot.unlink(missing_ok=True)
        self.bytes -= document.size

    def lookup(self, args: SourceArgs) -> Document | None:
        if args.document_id is not None:
            document = self.documents.get(args.document_id)
            if document is None:
                raise ToolError("DOCUMENT_EXPIRED", "snapshot expired or was released; read the path again")
            return document
        assert args.path is not None
        original = self.path(args.path)
        fingerprint = self.fingerprint(original)
        key = args.options.model_dump_json()
        return next(
            (
                d
                for d in self.documents.values()
                if d.original == original and d.fingerprint == fingerprint and d.options_key == key
            ),
            None,
        )

    def create(self, value: str, options: DocumentOptions) -> Document:
        original = self.path(value)
        fingerprint = self.fingerprint(original)
        size = fingerprint[0]
        if size > min(self.config.max_snapshot_bytes, self.config.max_snapshot_total_bytes):
            raise ToolError("DOCUMENT_TOO_LARGE", "file exceeds the configured snapshot size limit")
        selected = parser_options(original.suffix.lower()[1:], options, self.config)
        while len(self.documents) >= self.config.max_documents or self.bytes + size > self.config.max_snapshot_total_bytes:
            victim = next((d for d in self.documents.values() if not d.active), None)
            if victim is None:
                raise ToolError("CAPACITY_EXCEEDED", "all cached documents are in use")
            self.remove(victim.id)
        identifier = uuid.uuid4().hex
        snapshot = Path(self.directory.name) / (identifier + original.suffix.lower())
        digest = hashlib.sha256()
        copied = 0
        try:
            with original.open("rb") as source, snapshot.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > self.config.max_snapshot_bytes or copied > size:
                        raise ToolError("SOURCE_CHANGED", "file changed during snapshot creation; retry")
                    digest.update(chunk)
                    destination.write(chunk)
            if copied != size or self.fingerprint(original) != fingerprint:
                raise ToolError("SOURCE_CHANGED", "file changed during snapshot creation; retry")
        except BaseException:
            snapshot.unlink(missing_ok=True)
            raise
        document = Document(
            identifier,
            original,
            snapshot,
            digest.hexdigest(),
            fingerprint,
            options.model_dump_json(),
            selected,
            copied,
            time.monotonic(),
        )
        self.documents[identifier] = document
        self.bytes += copied
        return document

    @contextmanager
    def acquire(self, args: SourceArgs) -> Iterator[Document]:
        document = self.lookup(args)
        if document is None:
            assert args.path is not None
            document = self.create(args.path, args.options)
        document.touched = time.monotonic()
        self.documents.move_to_end(document.id)
        document.active += 1
        try:
            yield document
        finally:
            document.active -= 1

    def session(self, document: Document) -> Session:
        if document.session is None:
            sessions = [d for d in self.documents.values() if d.session is not None]
            if len(sessions) >= self.config.max_sessions:
                candidates = [d for d in sessions if not d.active]
                if not candidates:
                    raise ToolError("CAPACITY_EXCEEDED", "all cached sessions are in use")
                min(candidates, key=lambda d: d.session_touched).close_session()
            options = document.options
            if isinstance(options, DocxOptions):
                opened: Session = open_docx(document.snapshot, options=options)
            elif isinstance(options, PptxOptions):
                opened = open_pptx(document.snapshot, options=options)
            else:
                opened = open_xlsx(document.snapshot, options=options)
            opened.__enter__()
            document.session = opened
        document.session_touched = time.monotonic()
        return document.session

    def close(self) -> None:
        for document in list(self.documents.values()):
            self.remove(document.id)
        self.directory.cleanup()
