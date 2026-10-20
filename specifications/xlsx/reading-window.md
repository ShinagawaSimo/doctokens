# Reading windows

[XLSX](README.md) / Reading windows

Body results expose `selection.windows`, one entry per selected sheet. The same window determines the rendered rows and public metadata for one-shot parsing and session rendering. Search, query and resource operations retain their own selection contracts.

## Fields

### `sheet` and `requested_range`

- **Output**
  - Exact sheet name and the caller's range string, or `null` for a default preview.
- **Source**
  - Public `sheet` and `range_spec` arguments.
- **Parsing**
  - Explicit rectangles, whole rows and individual cells preserve saved source coordinates. Ranges never include another sheet. A default parser workbook result contains one window per sheet; the MCP tool selects only one sheet.

### `returned_range`

- **Output**
  - A1 rectangle bounding the selected saved cells, or `null` when no cells were selected. DTX `grid/@ref` uses these same bounds when a grid exists.
- **Source**
  - Retained cells in the actual window, including saved blanks and merge shadows.
- **Parsing**
  - Compute bounds after default trailing-blank removal and preview selection. Never include withheld tail rows in these bounds. Sparse holes remain holes; the rectangle does not claim a value at every coordinate. A density may suppress a retained cell, such as a DTX merge shadow or a plain hidden-column value.

### `cell_count` and `cell_limit`

- **Output**
  - Number of cells emitted by the selected density; threshold `500` for a default preview or `null` for an exact explicit range.
- **Parsing**
  - Structural/semantic count cells except merge shadows. Plain counts parsed values outside hidden columns, following its existing shadow behavior. Retained blank cells count when emitted; absent coordinates do not count. Hidden rows retain their existing density behavior.
  - Accumulate complete source rows. After the first row that brings the count to at least 500, stop before the following retained row. Do not split or omit the threshold row: 499 previous cells followed by a 10-cell row yields 509, and a first row with 700 cells yields 700. There is no second row after the threshold row.
  - The threshold governs cells, not characters or auxiliary sheet metadata. A long value or wide single row may exceed a small text budget. The MCP transport separately chunks large selected results.

### `truncated`, `next_row` and `next_cell`

- **Output**
  - Whether the default preview withheld remaining retained rows; next source row and its column-A coordinate, or `null` when no rows were withheld.
  - Truncated DTX grids also expose `truncated="true"` and `next-row`; plain appends `[Truncated: next row N]`.
- **Parsing**
  - Continuation points at the first withheld row, which can be beyond the preceding row plus one in sparse sheets. It is a public coordinate, not a stored cursor. Select the next explicit interval on the same sheet and snapshot.
  - Exact ranges always have `truncated=false` and null continuation. This means the request was fully selected; it does not state that the worksheet has no data beyond the request. Empty requests retain their requested range and have `returned_range=null`.
  - Result transport offsets address characters of one selected result and do not advance a data window. No implicit cross-sheet continuation is performed.

### `merged_ranges`

- **Output**
  - For each saved merge intersecting and crossing the window boundary: `ref`, `anchor` and `anchor_in_range`.
- **OOXML**
  - `worksheet/mergeCells/mergeCell/@ref`.
- **IR**
  - `SheetInfo.merge_refs`, independent of whether the anchor cell was materialized.
- **Parsing**
  - Compare the merge rectangle with the requested bounds, or with returned bounds for a default preview. Do not expand the selection or manufacture cells. Fully contained or disjoint merges need no crossing record.
  - Example: request `B1:C1` intersecting saved merge `A1:C1` reports `{"ref":"A1:C1","anchor":"A1","anchor_in_range":false}`. Read `A1` separately to obtain its content. Existing merge spans and shadow suppression remain applicable.
