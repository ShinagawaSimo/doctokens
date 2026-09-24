# Cell controls

[XLSX](../README.md) / Cell controls

The supported control is a saved checkbox state.

## Processing

Discover bags in styles.xml and paths containing featurepropertybag; use bag/featurePropertyBag local names. Parse failure caught by _parse_part yields no catalog warning. Plain checkbox rendering returns before appending ordinary cell comments.

## Fields

### `kind`

- **Output**
  - cell/@control=checkbox; plain `[Checkbox state]`.

- **OOXML**
  - Feature-property bag type Checkbox.

- **IR**
  - `CellControl.kind: str`

- **Parsing**
  - Resolve cell style through xfComplement → XFComplements mapping → XFComplement → XFControls → CellControl → Checkbox.

### `default`

- **Output**
  - cell/@default.

- **OOXML**
  - Checkbox bag property k=default.

- **IR**
  - `int`

- **Parsing**
  - int(value); missing/malformed 0.

### `value`

- **Output**
  - Internal displayed value.

- **OOXML**
  - Resolved cell text.

- **IR**
  - `str`

- **Parsing**
  - Copy current saved display text.

### `state`

- **Output**
  - cell/@state.

- **OOXML**
  - Resolved cell text.

- **IR**
  - `str`

- **Parsing**
  - Exact true → true; false → false; empty or other → empty. Does not toggle or evaluate control.


## Source references

- [CellControlCatalog.from_package](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L276)
- [_parse_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L578)
- [_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/plain.py#L61)
