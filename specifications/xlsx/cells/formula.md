# Formula text

[XLSX](../README.md) / Formula text

Formula output accompanies the saved display value.

## Fields

### `formula`

- **Output**
  - cell/@formula in XML densities.

- **OOXML**
  - s:c/s:f text.

- **IR**
  - `Cell.formula: str`

- **Parsing**
  - Store nonempty text; normal absent/empty f leaves no formula. Shared expansion can assign empty string; renderer omits falsey formula.

### `formulaType`

- **Output**
  - cell/@formula-type.

- **OOXML**
  - s:f/@t.

- **IR**
  - `str`

- **Parsing**
  - Store array or dataTable. Shared type is represented by si/shared_ref instead.

### `formulaRange`

- **Output**
  - cell/@formula-range.

- **OOXML**
  - s:f[@t="array"]/@ref.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty array range. dataTable ref is not copied by this parser.


## Source references

- [_formula_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L676)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L339)
