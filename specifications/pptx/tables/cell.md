# Table cells

[PPTX](../README.md) / Table cells

DTX omits continuation cells and retains origin spans.

## Fields

### `text`

- **Output**
  - `td` text.

- **OOXML**
  - a:tc/a:txBody.

- **IR**
  - `TableCell.text: str`

- **Parsing**
  - Use plain DrawingML text extraction; cell run formatting is not retained.

### `colSpan`

- **Output**
  - `td/@colspan` if !=1.

- **OOXML**
  - a:tc/@gridSpan.

- **IR**
  - `int`

- **Parsing**
  - Parse integer default 1; store only >1. Without explicit span, add contiguous hMerge cells to prior non-hMerge anchor.

### `rowSpan`

- **Output**
  - `td/@rowspan` if !=1.

- **OOXML**
  - a:tc/@rowSpan.

- **IR**
  - `int`

- **Parsing**
  - Parse integer default 1; store only >1. Without explicit origin span, vMerge cell extends nearest preceding non-vMerge cell at same array column.

### `hMerge`

- **Output**
  - Suppresses DTX td.

- **OOXML**
  - a:tc/@hMerge.

- **IR**
  - `bool`

- **Parsing**
  - DrawingML bool; retained only true.

### `vMerge`

- **Output**
  - Suppresses DTX td.

- **OOXML**
  - a:tc/@vMerge.

- **IR**
  - `bool`

- **Parsing**
  - DrawingML bool; retained only true.


## Source references

- [SlideObjectParser._normalize_table_merges](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/objects.py#L284)
- [_append_table_cells](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L189)
