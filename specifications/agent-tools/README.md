# Agent tools

The `doctokens-agent-tools` package provides one tool catalog and runtime for direct Python tool calls and optional MCP stdio.

- [Reading](reading.md): source selection, density, format windows, and parser options.
- [Ownership](ownership.md): snapshots, revision identity, sessions, caches, and limits.
- [Results](results.md): complete results, fragments, errors, and binary attachments.
- [MCP](mcp.md): transport projection and the executable entry point.

The runtime reads documents. It does not edit files, calculate formulas, refresh connections, perform retrieval/vectorization, or run a model/agent loop.

## Public Python interface

```python
from pathlib import Path
from doctokens_agent_tools import RuntimeConfig, ToolRuntime

with ToolRuntime(RuntimeConfig(allowed_roots=(Path("documents"),))) as runtime:
    definitions = [tool.to_dict() for tool in runtime.list_tools()]
    response = runtime.execute("read_docx", {"path": "report.docx", "density": "semantic"})
    result = response.to_dict()
```

`list_tools()` returns `ToolDefinition` objects with `name`, `description`, `input_schema`, and `output_schema`. The schemas are standard JSON Schema; provider-specific tool wrappers belong to the calling application.

`execute(name, arguments)` returns `ToolResponse`. `aexecute(name, arguments)` runs the same operation in a bounded thread executor. Runtime operations serialize access to owned snapshots and sessions; concurrent calls cannot close a session being read.

`ToolResponse.attachments` contains original `bytes` and MIME types for hosts to project into native model messages. `to_dict()` base64-encodes these attachments. MCP uses native content blocks instead.

## Tool catalog

| Tool | Operation |
| --- | --- |
| `inspect_document` | Public navigation or the lightweight workbook index |
| `read_docx` | Saved-page hint interval or explicit full document |
| `read_pptx` | Slide interval or explicit full presentation |
| `read_xlsx` | Workbook index, sheet, range, or explicit full workbook |
| `list_document_resources` | Full-session descriptors and supported operations |
| `read_resource` | Original embedded image/media bytes |
| `render_docx_resource` | Table, chart, or SmartArt DTX; table columns use header text |
| `render_pptx_resource` | Table, chart, or SmartArt DTX; table columns use zero-based indices |
| `render_xlsx_resource` | Chart or pivot-table summary DTX |
| `find_xlsx_cells` | Literal case-sensitive search over saved session data |
| `query_xlsx_data` | Experimental saved-data projection/filter/group/aggregate/order |
| `read_result` | Characters or bytes from an immutable stored result |
| `release_document` | Release snapshot, reader, and associated results |

## Compatibility

Parser 0.2.0 preserves the names and parameters of `render_resource`, `find_cells`, and `query_data`, but changes their result syntax from legacy markup to complete DTX 1.0. Main DTP/DTX output and the Python `parse_*` default selections are unchanged. `ParseResult` and `ResourceDescriptor` expose `to_dict()`; read sessions expose `describe()`. `inspect_xlsx()` reads only the workbook index. XLSX query argument types are exported from `xlsx_llm_parser`.
