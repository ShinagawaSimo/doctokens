"""Explicit ownership and failure cleanup shared by format read sessions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from typing import Generic, TypeVar

T = TypeVar("T")


class SessionLifecycle(Generic[T]):
    """Own one reader and parsed value, with a single enter/close lifecycle."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.value: T | None = None
        self._state = "new"
        self._stack = ExitStack()

    def check_new(self) -> None:
        if self._state != "new":
            raise RuntimeError(f"{self.label} session cannot be entered twice")

    def enter(self, reader: AbstractContextManager[object], parse: Callable[[], T]) -> T:
        self.check_new()
        try:
            self._stack.enter_context(reader)
            self.value = parse()
        except BaseException:
            self.close()
            raise
        self._state = "open"
        return self.value

    def require(self) -> T:
        if self._state != "open" or self.value is None:
            raise RuntimeError(f"{self.label} session is not open")
        return self.value

    def close(self) -> None:
        try:
            self._stack.close()
        finally:
            self.value = None
            self._state = "closed"
