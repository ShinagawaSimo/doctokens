# Rows

[XLSX](../README.md) / Rows

Row properties are copied to parsed cells and projected from the first cell of each emitted row.

## Fields

### `number`

- **Output**
  - tr/@number.

- **OOXML**
  - s:row/@r.

- **IR**
  - `RowAttrs.number`; `Cell.row: int`

- **Parsing**
  - int(r), default 0; zero/missing → previous effective row+1. Malformed noninteger row numbers raise ValueError.

### `hidden`

- **Output**
  - tr/@hidden=true.

- **OOXML**
  - s:row/@hidden.

- **IR**
  - `Cell.hidden: bool`

- **Parsing**
  - Store true only for "1"; plain output still includes hidden rows.

### `outlineLevel`

- **Output**
  - tr/@outline-level.

- **OOXML**
  - s:row/@outlineLevel.

- **IR**
  - `Cell.outlineLevel: int`

- **Parsing**
  - int(nonempty value), default 0; store only nonzero. Invalid integer raises ValueError.

### `collapsed`

- **Output**
  - tr/@collapsed=true.

- **OOXML**
  - s:row/@collapsed.

- **IR**
  - `Cell.collapsed: bool`

- **Parsing**
  - Store only if outlineLevel is nonzero and collapsed == "1".


## Source references

- [_row_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L568)
- [_apply_row_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L705)
- [_append_grid](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L244)
