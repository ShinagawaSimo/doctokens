# Tables

[PPTX](../README.md) / Tables

DrawingML tables preserve their cell merge declarations.

## Fields

### `id`

- **Output**
  - `table/@id` is slide-local shape ID.

- **OOXML**
  - Shape traversal.

- **IR**
  - `ShapeBlock.id`

- **Parsing**
  - Use shape ID, not table resource ID.

### `tableId`

- **Output**
  - Table resource key.

- **OOXML**
  - Parsed table order across slides.

- **IR**
  - `str`

- **Parsing**
  - table1, table2, ...; separate from shape ID.

### `rows`

- **Output**
  - DTX @rows and tr children; plain TSV rows.

- **OOXML**
  - a:tbl/a:tr/a:tc.

- **IR**
  - `list[list[str]]`

- **Parsing**
  - Extract `txBody` text per cell. DTX retains the first 30 rows; plain retains the first 10. Plain rows include continuation-cell text.

### `columns`

- **Output**
  - DTX @columns.

- **OOXML**
  - Parsed rows.

- **IR**
  - Derived int.

- **Parsing**
  - Maximum len(row), default 0; gridSpan does not enlarge this count.

### `columnWidths`

- **Output**
  - Internal column widths.

- **OOXML**
  - a:tblGrid/a:gridCol/@w.

- **IR**
  - `list[int]`

- **Parsing**
  - Keep positive integer values; malformed → 0 → discard; no DTX width output.

### `tableCells`

- **Output**
  - Detailed cell IR.

- **OOXML**
  - a:tc merge attributes.

- **IR**
  - `list[list[TableCell]]`

- **Parsing**
  - See [cells](cell.md).

### `truncated`

- **Output**
  - DTX @truncated=true; plain `[Table truncated: N rows, M cols]`.

- **OOXML**
  - Row count.

- **IR**
  - Derived bool.

- **Parsing**
  - True when row count exceeds30 DTX /10 plain; original row count remains in summary.


## Source references

- [SlideParser._table_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L686)
- [_append_table](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L177)
- [_shape_text](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/plain.py#L35)
