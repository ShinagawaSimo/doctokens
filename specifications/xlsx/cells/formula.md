# Formula text

[XLSX](../README.md) / Formula text

Formula output accompanies the saved display value.

## Fields

### `formula`

- **Output**
  - cell/@formula in XML densities.

- **OOXML**
  - s:c/s:f text.
  - For data tables, attributes on s:f[@t="dataTable"]; see [Data table formulas](data-table.md).

- **IR**
  - `Cell.formula: str`

- **Parsing**
  - Store nonempty text; normal absent/empty f leaves no formula. Shared expansion can assign empty string; renderer omits falsey formula.
  - Reconstruct data-table formulas as `TABLE(row_input,column_input)` without `=` or braces. Every retained result member has the same formula in IR; DTX emits it once per group in the rendered selection.

### `formulaType`

- **Output**
  - cell/@formula-type.

- **OOXML**
  - s:f/@t.

- **IR**
  - `str`

- **Parsing**
  - Store array or dataTable. Shared type is represented by si/shared_ref instead.
  - Data-table result members inherit the type from their master. Valid data-table group attributes are emitted together once per rendered selection.

### `formulaRange`

- **Output**
  - cell/@formula-range.

- **OOXML**
  - s:f[@t="array" or @t="dataTable"]/@ref.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty array or data-table result range. A data-table range excludes the trial-value headers and source formulas.
  - Retain the original data-table range when rendering only part of it; the first visible result cell carries the group definition even if the master was excluded.


## Source references

- [_formula_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/cells.py#L197)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L156)
