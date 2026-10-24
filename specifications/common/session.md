# Sessions

[COMMON](README.md) / Sessions

A session owns one open package and its parsed representation.

## Fields

### `open_*`

- **Output**
  - Context-managed format session.

- **OOXML**
  - `source` and format `ParseOptions`.

- **IR**
  - `DocxReadSession`, `PptxReadSession`, `XlsxReadSession`

- **Parsing**
  - Enter before reading; parse once; close the owned package on exit.
  - After a complete parse succeeds, discard the package's disposable source-byte cache. Keep the parsed representation, ZIP reader and relationship indexes available for repeated rendering and on-demand resource access. This does not force garbage collection or promise an immediate operating-system RSS decrease.

- **Diagnostics**
  - Use before enter or after close: `RuntimeError`.

### `memory_limit_bytes`

- **Source**
  - Optional keyword on `open_docx`, `open_pptx`, `open_xlsx` and their session constructors.
- **Default**
  - `None`: direct parser sessions do not enable estimated-memory admission.
- **Parsing**
  - A positive integer enables a session-local package reservation and growth
    checks. The estimate uses package part sizes and completed format fragments;
    it is not process RSS or an allocation guarantee. The algorithm and host
    aggregate ownership are defined in [tool ownership](../agent-tools/ownership.md).
  - Failure closes the package and discards the partial parsed value. The same
    session cannot be re-entered; create a new session to retry.
- **Diagnostics**
  - Invalid limits: `ValueError`. Estimated excess:
    `doctokens_core.ParseMemoryLimitError`, separate from invalid-package errors.

### `estimated_memory_bytes`

- **Output**
  - Integer estimate for an open session; zero when memory admission was disabled.
- **Parsing**
  - Reports the larger of source reservation and observed retained-data growth.
    It does not measure operating-system memory or add a process-wide cache.
- **Diagnostics**
  - Use before enter or after close: `RuntimeError`.

### `render`

- **Output**
  - `ParseResult` for selected density/window.

- **IR**
  - Existing parsed IR.

- **Parsing**
  - Apply format selection and renderer without a new package parse.

### `iter_render`

- **Output**
  - Iterator of output strings.

- **IR**
  - Existing parsed IR.

- **Parsing**
  - Iterates serialization, not a streaming OOXML parse. No constant-memory guarantee.

### `read_resource`

- **Output**
  - Original embedded bytes.

- **OOXML**
  - Resolved asset part.

- **Parsing**
  - DOCX: image. PPTX: image/media. XLSX: drawing image. External targets are not fetched.

- **Diagnostics**
  - Unsupported kind or external resource: `ValueError`; unknown ID: `KeyError`.

### `render_resource`

- **Output**
  - Explanatory `ParseResult`, `doctokens-xml/1.0`, `application/xml`, semantic density.

- **OOXML**
  - Parsed object record.

- **Parsing**
  - DOCX/PPTX: chart, SmartArt, table; XLSX: supported resource kinds described by its API. Arguments and text grammar are format-specific.

### `describe`

- **Output**
  - JSON-compatible format identity, navigation, and report.

- **Parsing**
  - DOCX exposes saved-hint `page_count` and `content_pages`; PPTX exposes `slide_count`, ordered slide numbers, hidden state and sections; XLSX exposes worksheet and table metadata.
  - Reads an entered session's parsed representation. XLSX also provides standalone `inspect_xlsx` for workbook metadata without parsing cells.
