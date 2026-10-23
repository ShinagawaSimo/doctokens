# Agent tools

The `doctokens-agent-tools` package provides one tool catalog and runtime for direct Python tool calls and optional MCP stdio.

- [Reading](reading.md): source selection, density, format windows, and parser options.
- [Text location](search.md): literal search with bounded excerpts and reusable coordinates.
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
| `get_runtime_info` | Active roots, result budgets, OCR availability and cache usage |
| `inspect_document` | Public navigation; stable lightweight XLSX index or explicit full_parse report |
| `read_docx` | Saved-page hint interval or explicit full document |
| `read_pptx` | Slide interval or explicit full presentation |
| `read_xlsx` | One worksheet; bounded default preview or exact cell/row range with sheet index |
| `list_document_resources` | Resource descriptors and supported operations; XLSX skips worksheet cells |
| `read_resource` | Original embedded image/media bytes |
| `render_docx_resource` | Table, chart, or SmartArt DTX; table columns use header text |
| `render_pptx_resource` | Table, chart, or SmartArt DTX; table columns use zero-based indices |
| `render_xlsx_resource` | Chart or pivot-table summary DTX |
| `find_xlsx_cells` | Literal case-sensitive search over saved session data |
| `find_document_text` | Bounded paragraph/cell excerpts with page/slide/cell locations |
| `query_xlsx_data` | Experimental saved-data projection/filter/group/aggregate/order |
| `read_result` | Characters or bytes from an immutable stored result |
| `release_document` | Release snapshot, reader, and associated results |

## Parser interfaces

`render_resource`, `find_cells`, and `query_data` return complete DTX 1.0.
`ParseResult` and `ResourceDescriptor` expose `to_dict()`; read sessions expose
`describe()` and bounded `find_text()`. `inspect_xlsx()` reads only the workbook
index; `XlsxResourceCatalog` reads resource metadata without cell data. XLSX query
argument types and `find_xlsx_text()` are exported from `xlsx_llm_parser`.
