# Cell hyperlinks

[XLSX](../README.md) / Cell hyperlinks

A hyperlink is attached to its source reference without evaluating it.

## Fields

### `hyperlink`

- **Output**
  - `cell/a/@href`.

- **OOXML**
  - s:hyperlinks/s:hyperlink/@ref,@r:id,@location.

- **IR**
  - `Cell.hyperlink: str`

- **Parsing**
  - Resolved relation target wins; append #location when nonempty. Without target, use #location. Neither → no link. Full-sheet parsing can create a blank target cell; a parse window only annotates existing selected cells. No missing-target warning.


## Source references

- [apply_hyperlink_specs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L89)
- [_ensure_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post_common.py#L23)
- [_append_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L204)
