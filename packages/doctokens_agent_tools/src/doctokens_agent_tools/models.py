"""Transport-neutral tool definitions, responses and native attachments."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


@dataclass(frozen=True)
class BinaryAttachment:
    data: bytes
    media_type: str


@dataclass
class ToolResponse:
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None
    attachments: tuple[BinaryAttachment, ...] = ()

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_dict(self, *, include_attachments: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {"ok": not self.is_error, "data": self.data}
        if self.error is not None:
            result["error"] = self.error
        if include_attachments and self.attachments:
            result["attachments"] = [
                {"media_type": a.media_type, "encoding": "base64", "data": base64.b64encode(a.data).decode("ascii")}
                for a in self.attachments
            ]
        return result
