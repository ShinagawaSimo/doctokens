# Cell controls

[XLSX](../README.md) / Cell controls

The supported control is a saved checkbox state.

## Processing

Discover XML bags in styles.xml and paths containing featurepropertybag; use bag/featurePropertyBag local names. Plain checkbox rendering returns before appending ordinary cell comments.

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
- **Diagnostics**
  - Malformed optional bag XML yields `XLSX_CATALOG_XML_INVALID`; the saved boolean cell value remains. A readable style with an `xfComplement` that cannot resolve to a bag yields `XLSX_CATALOG_REFERENCE_UNRESOLVED` when the bag catalog is absent. See [optional catalog diagnostics](../workbook/catalog-diagnostics.md).

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
  - Saved display text `TRUE` → state `true`; `FALSE` → state `false`; empty or other → state `empty`. The value retains the uppercase display text. Does not toggle or evaluate control.


## Source references

- [CellControlCatalog.from_package](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/features.py#L29)
- [_parse_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/cells.py#L42)
- [_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/plain.py#L61)
