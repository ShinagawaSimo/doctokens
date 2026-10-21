# MCP stdio

[Agent tools](README.md) / MCP

## Installation and startup

Install `doctokens-agent-tools[mcp]`. The `mcp` extra supplies the official Python SDK; the base package supports direct calls without importing MCP.

```console
doctokens-mcp --root /absolute/path/to/documents
```

The equivalent module command is `python -m doctokens_agent_tools.mcp --root ...`. Repeat `--root` for multiple allowed directories. The service requires initialization by an MCP client; it does not print document content as an ordinary command-line converter.

## Protocol mapping

- **Discovery**
  - `tools/list` exposes the shared catalog and generated input JSON Schemas. Body tools expose the `plain`, `structural`, and `semantic` density enum.
  - Schemas include source/query combinations, format-specific options and the
    active host's result budget. `get_runtime_info` provides active configuration.
- **Calls**
  - `tools/call` uses the same strict validation and execution as `ToolRuntime.execute`, including stable error codes.
  - Document text appears once in native `TextContent`. `structuredContent`
    carries `ok`/`data`/optional `error`, selection and continuation metadata.
    A part's `content_index` identifies its native text block. Metadata-only
    replies may have empty `content`; clients must consume structuredContent.
  - Large text reads return a first prefix immediately. Retain its result_id
    and continue from next_offset; do not restart at offset 0. Each continuation
    returns native text and only content_index/next_offset metadata. The final
    continuation has next_offset=null. Empty/unstarted parts have no text block.
  - A bounded application/json metadata result uses the same mechanism. Join
    its fragments and decode the resulting object before following its parts.
  - PNG/JPEG/WebP/GIF within the inline size cap return native image content.
    Other binary MIME types and images exceeding the cap return resource links
    without automatically embedding Base64. `resources/read` accepts only
    issued binary-result URIs and returns the original bytes on explicit request;
    URI lifetime follows the stored result and snapshot. The shared resource list
    is empty: callers discover URIs from their own binary tool responses.
- **Ownership**
  - One server connection owns one runtime. EOF, shutdown, or interruption releases its sessions and temporary snapshots. Logs go to stderr; stdout contains protocol messages only.
- **Transport**
  - The initial implementation supports stdio. HTTP, remote uploads, authentication, and multi-tenant isolation are outside this version.

## Direct connection example

```python
import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def collect_text(client, response, metadata):
    chunks = []
    if "content_index" in metadata:
        chunks.append(response.content[metadata["content_index"]].text)
    offset = metadata.get("next_offset")
    while offset is not None:
        response = await client.call_tool("read_result", {"result_id": metadata["result_id"], "offset": offset, "length": 32000})
        if response.isError:
            raise RuntimeError(response.structuredContent["error"])
        cursor = response.structuredContent["data"]
        chunks.append(response.content[cursor["content_index"]].text)
        offset = cursor["next_offset"]
    return "".join(chunks)


async def main():
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "doctokens_agent_tools.mcp", "--root", "/absolute/path/to/documents"],
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            result = await client.call_tool("read_docx", {"path": "report.docx", "density": "semantic"})
            if result.isError:
                raise RuntimeError(result.structuredContent["error"])
            data = result.structuredContent["data"]
            if data.get("media_type") == "application/json":
                data = json.loads(await collect_text(client, result, data))
            documents = [await collect_text(client, result, part) for part in data["parts"]]
            for document in documents:
                print(document)


asyncio.run(main())
```

Each DOCX page in `documents` is an independent XML document; concatenating roots
does not create a single valid XML document. Partial prefixes are not guaranteed
to be standalone XML or JSON. Source selection and character continuation are
separate operations.
