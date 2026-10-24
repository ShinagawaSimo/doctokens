"""Optional official-SDK MCP adapter and stdio command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
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
    from mcp.server.lowlevel.helper_types import ReadResourceContents

    from .mcp_output import project_response

    server: Server[Any, Any] = Server(
        "doctokens",
        version="0.1.0",
        instructions=(
            "Read paths directly; inspect only to discover navigation. DOCX pages are saved-render hints. "
            "Text appears once in content; structuredContent gives selection and content_index. "
            "Compatible mode also provides a separate native JSON metadata block; it is not document text. "
            "Root next_offset in search continues matches; per-part next_offset and read_result continue characters/bytes. "
            "Incomplete parts return result_id and next_offset: continue with read_result at that offset. "
            "Continuation next_offset=null ends the result; XML fragments are not standalone documents. "
            "DOCX/PPTX whole_document must be explicit. Use document_id for snapshot resource IDs."
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
        return project_response(response, runtime.config.mcp_output_mode)

    async def list_resources() -> list[types.Resource]:
        # Resource links are issued by binary tool responses, rather than exposing
        # an inventory of cached results belonging to unrelated selections.
        return []

    async def read_result_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        match = re.fullmatch(r"doctokens://result/([0-9a-f]{32})", str(uri))
        if match is None:
            raise ValueError("unsupported doctokens result URI")
        attachment = await runtime.aread_result_resource(match.group(1))
        return [ReadResourceContents(content=attachment.data, mime_type=attachment.media_type)]

    # The SDK list_tools registration decorator is currently untyped.
    server.list_tools()(list_tools)  # type: ignore[no-untyped-call]
    server.call_tool(validate_input=False)(call_tool)
    server.list_resources()(list_resources)  # type: ignore[no-untyped-call]
    server.read_resource()(read_result_resource)  # type: ignore[no-untyped-call]
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
    parser.add_argument("--max-session-memory-bytes", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--max-session-total-memory-bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--mcp-output-mode", choices=("compatible", "compact"), default="compatible")
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
            max_session_memory_bytes=args.max_session_memory_bytes,
            max_session_total_memory_bytes=args.max_session_total_memory_bytes,
            mcp_output_mode=args.mcp_output_mode,
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
