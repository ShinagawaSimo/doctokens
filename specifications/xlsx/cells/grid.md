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
  - Min/max rows and columns, including empty and shadow cells. Ignore worksheet dimension. Empty input has no grid.

### `truncated`

- **Output**
  - grid/@truncated=true.

- **OOXML**
  - Render budget.

- **IR**
  - Derived bool.

- **Parsing**
  - Whole-workbook DTX adds len(row) to count and appends that complete row; stops at >=500. Mark truncated only if nonempty rows remain. A row can exceed the budget; shadow cells count. Bounds include withheld rows. Selected sheet/range DTX disables budget.

### `cell`

- **Output**
  - Sparse tr/cell elements.

- **OOXML**
  - Cell list.

- **IR**
  - `SheetInfo.rows`

- **Parsing**
  - No rectangular blank-cell filling. Skip shadow cells in DTX; plain joins actual parsed cells with TAB, excluding hidden columns, and does not suppress shadow cells. Plain has no 500-cell cutoff.


## Source references

- [_append_grid](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L244)
- [_visible_bounds](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L403)
- [iter_plain_rows](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/plain.py#L19)
