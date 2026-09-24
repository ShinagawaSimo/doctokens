# Tables

[DOCX](../README.md) / Tables

A logical table can produce several page segments.

## Processing

Table block identity/page/section fields use [body](../document/body.md), [pagination](../document/pagination.md), and [sections](../document/section.md). Vertical-merge state survives segment boundaries. The table resource joins segments sharing tableId.

## Fields

### `id`

- **Output**
  - DTX `table/@id`; resource key.

- **OOXML**
  - Source `w:tbl` traversal.

- **IR**
  - `TableBlock.tableId: str`

- **Parsing**
  - Allocate `t1`, `t2`, ... per document, including nested tables. All segments of one table share this key.

### `segmentIndex`

- **Output**
  - Internal segment ordinal.

- **OOXML**
  - Row-level page changes.

- **IR**
  - `TableBlock.segmentIndex: int`

- **Parsing**
  - 1-based creation order; a changed page flushes already accumulated rows before the current row.

### `rows`

- **Output**
  - `table/tr`; DTP rows separated by LF.

- **OOXML**
  - Direct `w:tr` children.

- **IR**
  - `list[TableRow]`

- **Parsing**
  - Retain source order. Empty table produces no segments.

### `columns`

- **Output**
  - Nested-table `@columns`, plain truncation summary.

- **OOXML**
  - Sum of cell gridSpan values per row.

- **IR**
  - `TableBlock.columnCount: int`

- **Parsing**
  - Maximum row width observed by segment creation; current implementation does not use tblGrid to set this count.

### `truncated`

- **Output**
  - `table/@truncated="true"`, or plain truncation note.

- **OOXML**
  - Rendered segment row count.

- **IR**
  - Derived, not an OOXML flag.

- **Parsing**
  - DTX: >30 rows → first 2 rows. Plain: >10 rows → first row. Limits apply per segment. Nested DTX tables use a separate full-row path with no 30-row cutoff.


## Source references

- [TableParser.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/tables.py#L18)
- [TableParser._make_block](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/tables.py#L79)
- [_append_table](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L239)
- [_append_table_rows](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L283)
