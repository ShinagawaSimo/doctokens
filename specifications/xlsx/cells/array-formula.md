# Array formulas and spills

[XLSX](../README.md) / Array formulas and spills

Classic array ranges and dynamic spill associations have separate fields.

## Fields

### `dynamicArray`

- **Output**
  - Internal eligibility marker.

- **OOXML**
  - s:f[@t="array"]/@aca.

- **IR**
  - `Cell.dynamicArray: bool`

- **Parsing**
  - True exactly when aca == "1". Array formulas without it do not produce spill associations.

### `spillRange`

- **Output**
  - cell/@spill-range.

- **OOXML**
  - Array formulaRange on dynamic source.

- **IR**
  - `Cell.spillRange: str`

- **Parsing**
  - Require colon range extending beyond source cell; copy formulaRange. Does not evaluate spill size.

### `spillFrom`

- **Output**
  - Recipient cell/@spill-from.

- **OOXML**
  - Existing parsed cells within spillRange.

- **IR**
  - `Cell.spillFrom: str`

- **Parsing**
  - Set to source ref only if recipient has neither formula nor si. Do not create missing recipients or erase stored values.


## Source references

- [SheetWorkingSet.add_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L168)
- [apply_spill_sources](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L79)
