# Tables

[DOCX](../README.md) / Tables

A logical table can produce several page segments.

## Processing

Table block identity/page/section fields use [body](../document/body.md), [pagination](../document/pagination.md), and [sections](../document/section.md). Vertical-merge state survives segment boundaries. The table resource joins segments sharing tableId.

Select structural revisions and historical property sets before computing rows, columns, conditional styles, and merge relationships. Row/cell content controls and transparent wrappers are expanded at their own structural level without hoisting nested tables. Main output, full table resources, column queries, aggregation, and search share logical grid positions.

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
  - `w:tr` children, including rows wrapped in `sdt/sdtContent` or transparent containers.

- **IR**
  - `list[TableRow]`

- **Parsing**
  - Retain selected-view source order. Filter inserted/deleted rows according to revision_mode. Empty selected table produces no segments. Semantic review wraps affected rows in ins/del; row controls wrap the row without duplicating their text in each cell.

### `columns`

- **Output**
  - Nested-table `@columns`, plain truncation summary.

- **OOXML**
  - Selected `w:tblGrid/w:gridCol`, row gridBefore/gridAfter, and cell gridSpan values.

- **IR**
  - `TableBlock.columnCount: int`

- **Parsing**
  - Maximum of the selected table grid width and every selected row's `gridBefore + sum(gridSpan) + gridAfter`. Compute it for the whole logical table before pagination, so segments share the same count.
  - Omitted columns are positions without cells, not fabricated empty source cells. Plain output uses empty tab-delimited slots; XML records row grid-before/grid-after. Resource filters and aggregates match actual grid columns rather than the ordinal cell list.
- **Limits**
  - Reject a logical width above ParseOptions.max_table_columns before expanding padding or merge state; default 16384. This does not silently clamp the table.

### `truncated`

- **Output**
  - `table/@truncated="true"`, or plain truncation note.

- **OOXML**
  - Rendered segment row count.

- **IR**
  - Derived, not an OOXML flag.

- **Parsing**
  - DTX: >30 rows → first 2 rows. Plain: >10 rows → first row. Limits apply per segment. Nested DTX tables use a separate full-row path with no 30-row cutoff.
