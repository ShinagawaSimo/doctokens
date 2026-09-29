# Defined names

[XLSX](../README.md) / Defined names

Names retain their saved reference expressions without evaluation.

## Fields

### `name`

- **Output**
  - defined-name/@name.

- **OOXML**
  - s:definedName/@name.

- **IR**
  - `DefinedName.name: str`

- **Parsing**
  - Skip empty names. Sheet-scoped output suppresses _xlnm.* names; root global-name output does not apply that filter.

### `ref`

- **Output**
  - defined-name character data.

- **OOXML**
  - s:definedName text.

- **IR**
  - `DefinedName.ref: str`

- **Parsing**
  - Copy or empty; do not resolve references.

### `scopeSheet`

- **Output**
  - Placement at workbook root or sheet.

- **OOXML**
  - @localSheetId.

- **IR**
  - `str | None`

- **Parsing**
  - 0-based workbook sheet-list index; missing/malformed/out-of-range → None (global).

### `hidden`

- **Output**
  - Suppresses name output.

- **OOXML**
  - @hidden.

- **IR**
  - `bool`

- **Parsing**
  - Exactly "1" → true; otherwise false.


## Source references

- [_parse_workbook_xml](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/metadata.py#L32)
- [_scope_sheet_name](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/metadata.py#L108)
- [_append_workbook_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx_metadata.py#L14)
- [_append_sheet_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx_metadata.py#L31)
