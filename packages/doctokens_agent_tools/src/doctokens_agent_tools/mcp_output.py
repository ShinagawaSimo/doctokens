"""MCP-only projection: one body, with optional native navigation metadata."""

from __future__ import annotations

import base64
import json
from typing import Any, Literal

from mcp import types
from pydantic import AnyUrl

from .models import ToolResponse


def project_response(response: ToolResponse, mode: Literal["compatible", "compact"]) -> types.CallToolResult:
    structured = response.to_dict(include_attachments=False)
    data = dict(response.data)
    parts = [dict(part) for part in data.get("parts", [])]
    if "parts" in data:
        data["parts"] = parts
    structured["data"] = data
    content: list[types.TextContent | types.ImageContent | types.AudioContent | types.ResourceLink | types.EmbeddedResource] = []
    for payload in [data, *parts]:
        value = payload.pop("text", None)
        if value is None and payload.get("encoding") == "base64":
            value = payload.pop("data", None)
        if isinstance(value, str):
            payload["content_index"] = len(content)
            content.append(types.TextContent(type="text", text=value))

    # Separate native blocks keep JSON/XML fragments byte-for-byte reusable by
    # structured consumers. No wrapper is injected into the document body.
    native: dict[str, Any]
    if response.is_error:
        assert response.error is not None
        native = {"error": {key: response.error[key] for key in ("code", "message")}}
    else:
        native = {key: value for key, value in data.items() if key != "content_index"}
        if "parts" in native:
            native["parts"] = [{key: value for key, value in part.items() if key != "content_index"} for part in parts]
            if len(parts) > 1 and mode == "compatible":
                for part, metadata in zip(parts, native["parts"], strict=True):
                    if "content_index" in part:
                        metadata["content_index"] = part["content_index"] + 1
    if mode == "compatible" or response.is_error or not content:
        content.insert(0, types.TextContent(type="text", text=json.dumps(native, ensure_ascii=False, separators=(",", ":"))))
        for payload in [data, *parts]:
            if "content_index" in payload:
                payload["content_index"] += 1

    images = [a for a in response.attachments if a.media_type in {"image/png", "image/jpeg", "image/webp", "image/gif"}]
    if not images and (uri := response.data.get("resource_uri")):
        content.append(
            types.ResourceLink(
                type="resource_link",
                uri=AnyUrl(uri),
                name=response.data["result_id"],
                mimeType=response.data["media_type"],
                size=response.data["length"],
                description="Original binary bytes; expires with the result or document snapshot.",
            )
        )
    content.extend(
        types.ImageContent(type="image", data=base64.b64encode(attachment.data).decode("ascii"), mimeType=attachment.media_type)
        for attachment in images
    )
    return types.CallToolResult(content=content, structuredContent=structured, isError=response.is_error)
