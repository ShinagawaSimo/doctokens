# MCP stdio

[Agent tools](README.md) / MCP

## Installation and startup

Install `doctokens-agent-tools[mcp]`. The `mcp` extra supplies the official Python SDK; the base package supports direct calls without importing MCP.

```console
doctokens-mcp --root /absolute/path/to/documents
```

The equivalent module command is `python -m doctokens_agent_tools.mcp --root ...`. Repeat `--root` for multiple allowed directories. The service requires initialization by an MCP client; it does not print document content as an ordinary command-line converter.

`--mcp-output-mode compatible|compact` selects native metadata projection;
`compatible` is the default. `--max-session-memory-bytes` and
`--max-session-total-memory-bytes` configure the estimated session budgets, with
defaults 268435456 and 536870912. Host configuration is fixed until restart.
`--max-search-bytes`, `--max-search-states` and `--search-idle-seconds` configure
resumable XLSX text search with defaults 33554432, 8 and 600.

## Protocol mapping

- **Discovery**
  - `tools/list` exposes the shared catalog and generated input JSON Schemas. Body tools expose the `plain`, `structural`, and `semantic` density enum.
  - Schemas include source/query combinations, format-specific options and the
    active host's result budget. `get_runtime_info` provides active configuration.
- **Calls**
  - `tools/call` uses the same strict validation and execution as `ToolRuntime.execute`, including stable error codes.
  - Document text appears once in native `TextContent`. `structuredContent`
    carries `ok`/`data`/optional `error`, selection and continuation metadata.
    A part's `content_index` identifies its native body block in either mode.
  - In `compatible` mode, the first native text block is compact JSON navigation
    metadata, separate from document text. It exposes snapshot identity, selections,
    resource URIs and applicable continuation without serializing the body again.
    Multi-part replies also identify native body indices, including the absence
    of a block for an unstarted part. For one body, it follows the JSON block.
  - In `compact` mode, body replies omit that native metadata block. Structured
    clients must follow `content_index`, rather than assume block zero is a body.
    In both modes, metadata-only replies provide native JSON, and errors provide
    native error code/message as well as structured diagnostics and `isError=true`.
    No client-capability heuristic selects a mode. `RuntimeConfig.mcp_output_mode`
    provides the same choice for programmatic servers.
  - Large text reads return a first prefix immediately. Retain its result_id
    and continue from next_offset; do not restart at offset 0. Each continuation
    returns native text and only content_index/next_offset metadata. The final
    continuation has next_offset=null. Empty/unstarted parts have no text block.
    Search root next_offset continues matches; part next_offset and read_result
    continue characters/bytes. Native JSON metadata blocks are never joined into
    a document, JSON fragment or Base64 payload.
  - A bounded application/json metadata result uses the same mechanism. Join
    its fragments and decode the resulting object before following its parts.
  - PNG/JPEG/WebP/GIF within the inline size cap return native image content.
    Other binary MIME types and images exceeding the cap return resource links
    without automatically embedding Base64. `resources/read` accepts only
    issued binary-result URIs and returns the original bytes on explicit request;
    URI lifetime follows the stored result and snapshot. The shared resource list
    is empty: callers discover URIs from their own binary tool responses.
    Native-only consumers can read the accompanying URI/encoding metadata and
    use explicit resources/read or the existing read_result fallback.
- **Ownership**
  - One server connection owns one runtime. EOF, shutdown, or interruption releases its sessions and temporary snapshots. Logs go to stderr; stdout contains protocol messages only.
- **Cancellation and progress**
  - MCP cancellation signals a request-local ParseControl, including when its
    handler is cancelled while awaiting an executor future. The worker checks
    package I/O, worksheet rows, DOCX blocks, slides, matching/query/render loops
    and result admission, then unwinds owned resources. Completed caches are
    preserved; no partial session is committed. An already completed session may
    survive a later cancelled rendering request.
  - Send progress only when the request supplies a progressToken. Notifications
    report throttled phases and a monotonically increasing sequence, at most once
    per 250 ms; they have no invented percentage/total and never enter body text.
    No progress token means no progress notifications. External OCR calls and
    native operations without checkpoints remain non-preemptible until return.
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
