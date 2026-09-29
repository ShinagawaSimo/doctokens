# Merged cells

[XLSX](../README.md) / Merged cells

Merge ranges describe existing cells; they do not fill missing cells.

## Fields

### `colspan`

- **Output**
  - cell/@colspan if !=1.

- **OOXML**
  - s:mergeCells/s:mergeCell/@ref.

- **IR**
  - `Cell.colspan: int`

- **Parsing**
  - For existing top-left anchor: end_col-start_col+1; single-reference ranges without colon are ignored.

### `rowspan`

- **Output**
  - cell/@rowspan if !=1.

- **OOXML**
  - Same merge range.

- **IR**
  - `Cell.rowspan: int`

- **Parsing**
  - For existing anchor: end_row-start_row+1.

### `shadow`

- **Output**
  - Suppresses DTX cell.

- **OOXML**
  - Existing non-origin cells covered by merge.

- **IR**
  - `Cell.shadow: bool`

- **Parsing**
  - Mark true even if anchor is absent. Later overlapping merge declarations can overwrite origin spans. No overlap diagnostic is emitted.


## Source references

- [apply_merge_refs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L30)
- [_append_grid](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L62)
