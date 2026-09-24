# Data validation

[XLSX](../README.md) / Data validation

Validation declarations are extracted without enforcing cell constraints.

## Fields

### `ranges`

- **Output**
  - data-validation/@ref.

- **OOXML**
  - s:dataValidations/s:dataValidation/@sqref.

- **IR**
  - `DataValidation.ranges: str`

- **Parsing**
  - Copy, default empty.

### `type`

- **Output**
  - data-validation/@type.

- **OOXML**
  - @type.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty.

### `formula1`

- **Output**
  - Internal constraint formula; no DTX projection.

- **OOXML**
  - s:formula1 text.

- **IR**
  - `str`

- **Parsing**
  - Copy, default empty; no evaluation.

### `allowBlank`

- **Output**
  - Internal flag; no DTX projection.

- **OOXML**
  - @allowBlank.

- **IR**
  - `bool`

- **Parsing**
  - Default true; exactly 1 → true.


## Source references

- [_parse_data_validations_element](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L457)
- [_append_sheet_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L79)
