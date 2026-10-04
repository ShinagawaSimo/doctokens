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
  - Min/max rows and columns of the reading projection, including retained empty and shadow cells. Ignore worksheet dimension. Empty input has no grid.

### `truncated`

- **Output**
  - grid/@truncated=true.

- **OOXML**
  - Render budget.

- **IR**
  - Derived bool.

- **Parsing**
  - Whole-workbook DTX removes disposable trailing blanks before budgeting, adds len(row) to count and appends that complete row; stops at >=500. Mark truncated only if projected rows remain. A row can exceed the budget; retained shadow cells count. Bounds include withheld projected rows. Selected sheet/range DTX disables budget.

### `cell`

- **Output**
  - Sparse tr/cell elements.

- **OOXML**
  - Cell list.

- **IR**
  - `SheetInfo.rows`

- **Parsing**
  - No rectangular blank-cell filling. Skip shadow cells in DTX; plain joins actual parsed cells with TAB, excluding hidden columns, and does not suppress shadow cells. Plain has no 500-cell cutoff.
  - Whole-workbook and whole-sheet reading omit saved numeric empty cells beyond the maximum meaningful row or column, only when they have no value, inline text, formula, metadata, visible fill/border or nondefault protection. A number format alone is not visible content on a blank cell. Retain internal blanks and original coordinates.
  - Retain associated blanks for comments, hyperlinks, merged/shadow cells, formula result ranges, rich values and controls. Preserve potential conditional-format anchors and visible row/column styling conservatively without evaluating conditional rules. This decision uses source information even when a lower density does not display the associated attribute.
  - Explicit range reads retain the saved cells within their requested source coordinates, including blank placeholders. The reading projection does not mutate parsed rows, search/query inputs or query row counts.


## Source references

- [_append_grid](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L65)
- [_visible_bounds](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L236)
- [iter_plain_rows](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/plain.py#L20)
- [Reading extent projection](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/reading_rows.py)
- [Blank association preservation](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/blank_cells.py)
