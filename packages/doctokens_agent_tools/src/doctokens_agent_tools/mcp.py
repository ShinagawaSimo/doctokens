"""Optional official-SDK MCP adapter and stdio command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import AnyUrl

from .config import RuntimeConfig
from .runtime import ToolRuntime

if TYPE_CHECKING:
    from mcp.server import Server


def build_server(runtime: ToolRuntime) -> Server[Any, Any]:
    from mcp import types
    from mcp.server import Server

    server: Server[Any, Any] = Server(
        "doctokens",
        version="0.1.0",
        instructions=(
            "Inspect the document, then read explicit page/slide/cell intervals. "
            "DOCX pages are saved-render hints. Use document_id for resource IDs from that snapshot. "
            "Large results return result_id: call read_result until next_offset is null. "
            "Fragments are not standalone XML; whole_document must be explicitly requested."
        ),
    )

    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=d.name,
                description=d.description,
                inputSchema=d.input_schema,
                outputSchema=d.output_schema,
                annotations=types.ToolAnnotations(
                    readOnlyHint=True, destructiveHint=False, openWorldHint=runtime.config.ocr_provider is not None
                ),
            )
            for d in runtime.list_tools()
        ]

    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        response = await runtime.aexecute(name, arguments)
        structured = response.to_dict(include_attachments=False)
        content: list[
            types.TextContent | types.ImageContent | types.AudioContent | types.ResourceLink | types.EmbeddedResource
        ] = [types.TextContent(type="text", text=json.dumps(structured, ensure_ascii=False))]
        for attachment in response.attachments:
            data = base64.b64encode(attachment.data).decode("ascii")
            if attachment.media_type in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                content.append(types.ImageContent(type="image", data=data, mimeType=attachment.media_type))
            else:
                identifier = response.data["result_id"]
                content.append(
                    types.EmbeddedResource(
                        type="resource",
                        resource=types.BlobResourceContents(
                            uri=AnyUrl(f"doctokens://result/{identifier}"), mimeType=attachment.media_type, blob=data
                        ),
                    )
                )
        return types.CallToolResult(content=content, structuredContent=structured, isError=response.is_error)

    # The SDK list_tools registration decorator is currently untyped.
    server.list_tools()(list_tools)  # type: ignore[no-untyped-call]
    server.call_tool(validate_input=False)(call_tool)
    return server


async def serve(config: RuntimeConfig) -> None:
    from mcp.server.stdio import stdio_server

    with ToolRuntime(config) as runtime:
        server = build_server(runtime)
        async with stdio_server() as (reader, writer):
            await server.run(reader, writer, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Office documents over MCP stdio.")
    parser.add_argument("--root", action="append", required=True, type=Path, help="Allowed directory; repeat for multiple roots.")
    parser.add_argument("--reply-chars", type=int, default=12_000)
    parser.add_argument("--max-sessions", type=int, default=4)
    parser.add_argument("--max-documents", type=int, default=32)
    parser.add_argument("--idle-seconds", type=float, default=600)
    parser.add_argument("--result-idle-seconds", type=float, default=600)
    parser.add_argument("--max-result-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-snapshot-bytes", type=int, default=128 * 1024 * 1024)
    parser.add_argument("--max-snapshot-total-bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        config = RuntimeConfig(
            allowed_roots=tuple(args.root),
            reply_chars=args.reply_chars,
            max_sessions=args.max_sessions,
            max_documents=args.max_documents,
            idle_seconds=args.idle_seconds,
            result_idle_seconds=args.result_idle_seconds,
            max_result_bytes=args.max_result_bytes,
            max_snapshot_bytes=args.max_snapshot_bytes,
            max_snapshot_total_bytes=args.max_snapshot_total_bytes,
            workers=args.workers,
        )
        asyncio.run(serve(config))
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            parser.error("MCP support is not installed; install doctokens-agent-tools[mcp]")
        raise
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
