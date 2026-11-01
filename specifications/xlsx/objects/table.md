# Declared tables

[XLSX](../README.md) / Declared tables

Excel ListObjects supply range and column metadata independently of the cell grid.

## Processing

Missing target → TABLE_PART_MISSING; XML error → TABLE_XML_INVALID; failed table omitted.

## Fields

### `id`

- **Output**
  - table-summary/@id; resource key.

- **OOXML**
  - Accepted table relationship order across sheets.

- **IR**
  - `TableInfo.id: str`

- **Parsing**
  - table-0, table-1, ...; counter advances for accepted tables only.

### `name`

- **Output**
  - table-summary/@name; plain `[Table name ref]` label when known.

- **OOXML**
  - table/@displayName, fallback @name.

- **IR**
  - `str`

- **Parsing**
  - Attribute fallback applies only when displayName is absent; default empty.

### `ref`

- **Output**
  - table-summary/@ref; source range in the plain table label when known.

- **OOXML**
  - table/@ref.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `columns`

- **Output**
  - Semantic table-summary/column text in source order. Plain labels omit the list; saved grid
    headers remain ordinary cell content, emitted once.

- **OOXML**
  - tableColumns/tableColumn/@name.

- **IR**
  - `list[str]`

- **Parsing**
  - Keep parsed names in source order, with one element per name and no
    delimiter interpretation. Commas and other punctuation remain literal.

### `totalsRow`

- **Output**
  - Semantic @totals-row=true.

- **OOXML**
  - table/@totalsRowCount.

- **IR**
  - `bool`

- **Parsing**
  - int>=1; missing/invalid → false. totalsRowShown is not used.
