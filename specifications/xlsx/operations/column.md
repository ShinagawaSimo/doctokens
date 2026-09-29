# Query columns

[XLSX](../README.md) / Query columns

Column references resolve against a query-local catalog.

## Fields

### `key`

- **Output**
  - Internal stable query key.

- **Source**
  - Header/table column label.

- **IR**
  - `QueryColumn.key: str`

- **Parsing**
  - Strip label; empty → __colN; repeated base → base_2,base_3,...

### `label`

- **Output**
  - Output th text.

- **Source**
  - Header/table column label.

- **IR**
  - `str`

- **Parsing**
  - Stripped source label; can be empty.

### `col`

- **Output**
  - Internal source coordinate.

- **Source**
  - Selected range column.

- **IR**
  - `int`

- **Parsing**
  - 1-based source column; computed aggregate columns use0.

### `selector`

- **Output**
  - Resolves API column argument.

- **Source**
  - Call string.

- **IR**
  - Resolved key.

- **Parsing**
  - First exact key or label match; then column letter or ColN. Unknown → ValueError. First matching duplicate label wins.


## Source references

- [_columns_from_labels](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L163)
- [_resolve_column_key](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/query.py#L249)
