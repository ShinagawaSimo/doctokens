"""Versioned local snapshots and bounded ownership of parser sessions."""

from __future__ import annotations

import hashlib
import tempfile
import time
import uuid
from _thread import RLock
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any

from doctokens_word import DocxReadSession
from doctokens_word import ParseOptions as DocxOptions
from doctokens_core.execution import checkpoint
from doctokens_core.models import ResourceDescriptor
from doctokens_powerpoint import ParseOptions as PptxOptions
from doctokens_powerpoint import PptxReadSession
from doctokens_excel import ParseOptions as XlsxOptions
from doctokens_excel import XlsxReadSession

from .config import RuntimeConfig
from .models import ToolError
from .options import parser_options
from .schemas import BaseOptions, BaseSourceArgs, DocumentOptions
from .sessions import admit_session

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
    session_memory_bytes: int = 0
    session_reservation: int | None = None
    active: int = 0
    index: dict[str, Any] | None = None
    resource_catalog: tuple[ResourceDescriptor, ...] | None = None
    operation_lock: RLock = field(default_factory=RLock)
    session_loading: bool = False

    @property
    def format(self) -> str:
        return self.original.suffix.lower()[1:]

    def close_session(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None
        self.session_memory_bytes = 0


class DocumentStore:
    """Called under the runtime lock; leases protect active snapshots."""

    def __init__(self, config: RuntimeConfig, lock: RLock | None = None) -> None:
        self.config = config
        self.lock = lock or RLock()
        self.before_remove: Callable[[str], None] | None = None
        self.before_session: Callable[[str], None] | None = None
        self.directory = tempfile.TemporaryDirectory(prefix="doctokens-tools-")
        self.documents: OrderedDict[str, Document] = OrderedDict()
        self.bytes = 0
        self.pending_bytes = 0
        self._pending: dict[tuple[Path, tuple[int, int, int], str], Event] = {}

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
        document = self.documents[identifier]
        if document.active:
            raise ToolError("DOCUMENT_BUSY", "document is being read; cancel or finish the read before releasing it")
        if self.before_remove is not None:
            self.before_remove(identifier)
        self.documents.pop(identifier)
        document.close_session()
        document.snapshot.unlink(missing_ok=True)
        self.bytes -= document.size

    def lookup(self, args: BaseSourceArgs) -> Document | None:
        if args.document_id is not None:
            document = self.documents.get(args.document_id)
            if document is None:
                raise ToolError("DOCUMENT_EXPIRED", "snapshot expired or was released; read the path again")
            return document
        assert args.path is not None
        original = self.path(args.path)
        fingerprint = self.fingerprint(original)
        key = _options_key(args.options)
        return next(
            (
                d
                for d in self.documents.values()
                if d.original == original and d.fingerprint == fingerprint and d.options_key == key
            ),
            None,
        )

    def create(self, value: str, options: BaseOptions, *, lease: bool = False) -> Document:
        original = self.path(value)
        options_key = _options_key(options)
        selected = parser_options(original.suffix.lower()[1:], options, self.config)
        while True:
            checkpoint("admitting snapshot")
            fingerprint = self.fingerprint(original)
            size = fingerprint[0]
            key = (original, fingerprint, options_key)
            with self.lock:
                existing = next(
                    (
                        d
                        for d in self.documents.values()
                        if d.original == original and d.fingerprint == fingerprint and d.options_key == options_key
                    ),
                    None,
                )
                if existing is not None:
                    existing.touched = time.monotonic()
                    self.documents.move_to_end(existing.id)
                    existing.active += int(lease)
                    return existing
                pending = self._pending.get(key)
                if pending is None:
                    if size > min(self.config.max_snapshot_bytes, self.config.max_snapshot_total_bytes):
                        raise ToolError("DOCUMENT_TOO_LARGE", "file exceeds the configured snapshot size limit")
                    while (
                        len(self.documents) + len(self._pending) >= self.config.max_documents
                        or self.bytes + self.pending_bytes + size > self.config.max_snapshot_total_bytes
                    ):
                        victim = next((d for d in self.documents.values() if not d.active), None)
                        if victim is None:
                            raise ToolError("CAPACITY_EXCEEDED", "all cached documents are in use")
                        self.remove(victim.id)
                    pending = Event()
                    self._pending[key] = pending
                    self.pending_bytes += size
                    break
            while not pending.wait(0.05):
                checkpoint("waiting for snapshot")
        identifier = uuid.uuid4().hex
        snapshot = Path(self.directory.name) / (identifier + original.suffix.lower())
        digest = hashlib.sha256()
        copied = 0
        committed = False
        try:
            with original.open("rb") as source, snapshot.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    checkpoint("creating snapshot")
                    copied += len(chunk)
                    if copied > self.config.max_snapshot_bytes or copied > size:
                        raise ToolError("SOURCE_CHANGED", "file changed during snapshot creation; retry")
                    digest.update(chunk)
                    destination.write(chunk)
            if copied != size or self.fingerprint(original) != fingerprint:
                raise ToolError("SOURCE_CHANGED", "file changed during snapshot creation; retry")
            checkpoint("snapshot ready")
            document = Document(
                identifier,
                original,
                snapshot,
                digest.hexdigest(),
                fingerprint,
                options_key,
                selected,
                copied,
                time.monotonic(),
                active=int(lease),
            )
            with self.lock:
                self.documents[identifier] = document
                self.bytes += copied
                committed = True
            return document
        finally:
            try:
                if not committed:
                    snapshot.unlink(missing_ok=True)
            finally:
                with self.lock:
                    self.pending_bytes -= size
                    self._pending.pop(key, None)
                    pending.set()

    @contextmanager
    def acquire(self, args: BaseSourceArgs) -> Iterator[Document]:
        with self.lock:
            document = self.lookup(args)
            if document is not None:
                document.touched = time.monotonic()
                self.documents.move_to_end(document.id)
                document.active += 1
        if document is None:
            assert args.path is not None
            document = self.create(args.path, args.options, lease=True)
        try:
            yield document
        finally:
            with self.lock:
                document.active -= 1

    def session(self, document: Document) -> Session:
        if document.session is None:
            if self.before_session is not None:
                self.before_session(document.id)
            admit_session(document, self.documents.values(), self.config, self.lock)
        document.session_touched = time.monotonic()
        assert document.session is not None
        return document.session

    def close(self) -> None:
        for document in list(self.documents.values()):
            self.remove(document.id)
        self.directory.cleanup()


def _options_key(options: BaseOptions) -> str:
    return DocumentOptions.model_validate(options.model_dump()).model_dump_json()
