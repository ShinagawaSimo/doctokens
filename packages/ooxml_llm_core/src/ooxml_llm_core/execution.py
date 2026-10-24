"""Caller-owned cooperative cancellation and optional throttled phase progress."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from io import BufferedReader
from threading import Event
from zipfile import ZipExtFile


class ParseCancelled(BaseException):
    """Cancellation must bypass content-recovery handlers, then unwind owners."""


class CheckedReader(BufferedReader):
    def __init__(self, source: ZipExtFile) -> None:
        super().__init__(source)

    def read(self, size: int | None = -1) -> bytes:
        checkpoint("reading package bytes")
        value = super().read(size)
        checkpoint("reading package bytes")
        return value


class ParseControl:
    def __init__(self, progress: Callable[[float, str], None] | None = None) -> None:
        self.id = uuid.uuid4().hex
        self.cancelled = Event()
        self.progress = progress
        self._last_progress = 0.0
        self._sequence = 0

    def cancel(self) -> None:
        self.cancelled.set()

    def check(self, stage: str = "reading") -> None:
        if self.cancelled.is_set():
            raise ParseCancelled()
        if self.progress is not None and time.monotonic() - self._last_progress >= 0.25:
            self._last_progress = time.monotonic()
            self._sequence += 1
            self.progress(float(self._sequence), stage)


_CONTROL: ContextVar[ParseControl | None] = ContextVar("doctokens_parse_control", default=None)


def current_control() -> ParseControl | None:
    return _CONTROL.get()


def checkpoint(stage: str = "reading") -> None:
    control = _CONTROL.get()
    if control is not None:
        control.check(stage)


@contextmanager
def parse_scope(control: ParseControl) -> Iterator[None]:
    token = _CONTROL.set(control)
    try:
        control.check()
        yield
    finally:
        _CONTROL.reset(token)
