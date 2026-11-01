"""MCP-only projection: one body, with optional native navigation metadata."""

from __future__ import annotations

import base64
import json
from typing import Any

from mcp import types
from pydantic import AnyUrl

from ..contracts.models import ToolResponse


def project_response(response: ToolResponse) -> types.CallToolResult:
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

    if response.is_error or not content:
        native: dict[str, Any]
        if response.is_error:
            assert response.error is not None
            native = {"error": {key: response.error[key] for key in ("code", "message")}}
        else:
            native = data
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
