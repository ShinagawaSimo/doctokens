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
- **Calls**
  - `tools/call` uses the same strict validation and execution as `ToolRuntime.execute`, including stable error codes.
  - JSON responses are returned as both `structuredContent` and a compatibility text content block. Inline binary bytes appear separately as native content, not inside structured JSON.
- **Ownership**
  - One server connection owns one runtime. EOF, shutdown, or interruption releases its sessions and temporary snapshots. Logs go to stderr; stdout contains protocol messages only.
- **Transport**
  - The initial implementation supports stdio. HTTP, remote uploads, authentication, and multi-tenant isolation are outside this version.

## Direct connection example

```python
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

parameters = StdioServerParameters(
    command=sys.executable,
    args=["-m", "doctokens_agent_tools.mcp", "--root", "/absolute/path/to/documents"],
)
async with stdio_client(parameters) as (reader, writer):
    async with ClientSession(reader, writer) as client:
        await client.initialize()
        tools = await client.list_tools()
        result = await client.call_tool("read_docx", {"path": "report.docx", "density": "semantic"})
```
