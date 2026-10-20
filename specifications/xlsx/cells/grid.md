# Grid projection

[XLSX](../README.md) / Grid projection

DTX emits sparse cells with row and column coordinates.

## Fields

### `ref`

- **Output**
  - grid/@ref, always A1:B2 form.

- **OOXML**
  - All parsed cells.

- **IR**
  - Derived coordinate bounds.

- **Parsing**
  - Min/max rows and columns of the actual returned window, including retained empty and shadow cells. Exclude withheld tail rows. Ignore worksheet dimension. Empty input has no grid.

### `truncated`

- **Output**
  - grid/@truncated=true.

- **OOXML**
  - Render budget.

- **IR**
  - Derived bool.

- **Parsing**
  - Default workbook/sheet reading removes disposable trailing blanks, counts emitted cells and finishes the row that reaches 500. Mark truncated only if retained rows remain and expose the first withheld row as `grid/@next-row`. Shadows do not count in DTX. The final row may exceed the threshold. Explicit ranges disable this preview threshold in all densities. See [reading windows](../reading-window.md).

### `cell`

- **Output**
  - Sparse tr/cell elements.

- **OOXML**
  - Cell list.

- **IR**
  - `SheetInfo.rows`

- **Parsing**
  - No rectangular blank-cell filling. Skip shadow cells in DTX; plain joins actual parsed cells with TAB, excluding hidden columns, and does not suppress shadow cells. All densities use a default 500-cell threshold while preserving the entire final row.
  - Whole-workbook and whole-sheet reading omit saved numeric empty cells beyond the maximum meaningful row or column, only when they have no value, inline text, formula, metadata, visible fill/border or nondefault protection. A number format alone is not visible content on a blank cell. Retain internal blanks and original coordinates.
  - Retain associated blanks for comments, hyperlinks, merged/shadow cells, formula result ranges, rich values and controls. Preserve potential conditional-format anchors and visible row/column styling conservatively without evaluating conditional rules. This decision uses source information even when a lower density does not display the associated attribute.
  - Explicit range reads retain the saved cells within their requested source coordinates, including blank placeholders. The reading projection does not mutate parsed rows, search/query inputs or query row counts.
