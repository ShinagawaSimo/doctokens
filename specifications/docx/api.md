# Parsing and selection

[DOCX](README.md) / Parsing and selection

The public functions return [ParseResult](../common/result.md); sessions follow the [common lifetime](../common/session.md).

## Synopsis

```python
def parse_docx(
    source: Source,
    *,
    density: Density | str = "semantic",
    page_hint: int | None = None,
    span: int = 1,
    options: ParseOptions | None = None,
) -> ParseResult: ...
```

## Fields

### `source`

- **Output**
  - Input to parse_docx/open_docx.

- **Source**
  - DOCX OPC package.

- **IR**
  - `str | Path | bytes`

- **Parsing**
  - Path or complete ZIP bytes.

### `density`

- **Output**
  - DTP or DTX projection.

- **Source**
  - Call argument.

- **IR**
  - `"plain" | "structural" | "semantic"`

- **Parsing**
  - Default semantic. One-shot lower densities use summary extraction; sessions retain full details, so later lower-density renderings can contain richer chart summaries.

### `page_hint`

- **Output**
  - Page-window selection.

- **Source**
  - Call argument.

- **IR**
  - `int | None`

- **Parsing**
  - None → all; -1 → last stored page; positive int → starting page. Reject bool, 0, and values below -1. Missing start or page beyond end yields empty body projection. Stop a multi-page window at the first page with no indexed content.

### `span`

- **Output**
  - Number of pages requested.

- **Source**
  - Call argument.

- **IR**
  - `int = 1`

- **Parsing**
  - Positive non-bool int; span other than 1 requires page_hint. Window rendering removes headers, footers, comments; retains assets and notes from the parsed document.

### `preserve_empty_paragraphs`

- **Output**
  - Controls empty body paragraphs.

- **Source**
  - ParseOptions.

- **IR**
  - `bool = False`

- **Parsing**
  - Retain otherwise empty paragraphs when true.

### `include_runs`

- **Output**
  - Controls detailed body runs.

- **Source**
  - ParseOptions.

- **IR**
  - `bool = True`

- **Parsing**
  - False uses text/pageSegments; inline objects/format detail can be unavailable to renderers.

### `include_raw_hints`

- **Output**
  - Internal diagnostic hints.

- **Source**
  - ParseOptions.

- **IR**
  - `bool = True`

- **Parsing**
  - Requires RAW_HINTS plan; semantic one-shot does not include that feature, session does.

### `revision_mode`

- **Output**
  - Selected revision text.

- **Source**
  - ParseOptions.

- **IR**
  - `RevisionMode = FINAL`

- **Parsing**
  - See [revisions](text/revision.md).

### `ocr`

- **Output**
  - Optional adapter.

- **Source**
  - ParseOptions.

- **IR**
  - `object | None = None`

- **Parsing**
  - See [OCR](../common/ocr.md).

### `ocr_workers`

- **Output**
  - OCR concurrency.

- **Source**
  - ParseOptions.

- **IR**
  - `int = 4`

- **Parsing**
  - Common OCR validation.

### `ocr_timeout`

- **Output**
  - OCR timeout.

- **Source**
  - ParseOptions.

- **IR**
  - `float = 120.0`

- **Parsing**
  - Common OCR validation; seconds.


## Source references

- [parse_docx](../../packages/docx_llm_parser/src/docx_llm_parser/api.py)
- [DocxReadSession](../../packages/docx_llm_parser/src/docx_llm_parser/api.py)
- [render_page_window](../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dispatch.py#L34)
- [ParseOptions](../../packages/docx_llm_parser/src/docx_llm_parser/core/models/document.py#L38)
