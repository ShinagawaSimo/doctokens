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
  - Explanatory `ParseResult`, `legacy-markup/0`, `text/plain`.

- **OOXML**
  - Parsed object record.

- **Parsing**
  - DOCX/PPTX: chart, SmartArt, table; XLSX: supported resource kinds described by its API. Arguments and text grammar are format-specific.


## Source references

- [DocxReadSession](../../packages/docx_llm_parser/src/docx_llm_parser/api.py#L101)
- [PptxReadSession](../../packages/pptx_llm_parser/src/pptx_llm_parser/api.py#L126)
- [XlsxReadSession](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L114)
