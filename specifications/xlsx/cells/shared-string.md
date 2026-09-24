# Shared strings

[XLSX](../README.md) / Shared strings

The shared-string index is the source si ordinal.

## Fields

### `text`

- **Output**
  - Resolved cell display text.

- **OOXML**
  - xl/sharedStrings.xml/s:sst/s:si.

- **IR**
  - `list[str]`

- **Parsing**
  - If direct t exists, use its text only. Otherwise concatenate direct r/t texts in order. Missing part → empty catalog.

### `index`

- **Output**
  - Internal lookup position.

- **OOXML**
  - Cell t=s with v integer.

- **IR**
  - 0-based shared string index.

- **Parsing**
  - Accept only 0 <= index < len(strings); invalid integer or bounds yields empty display text.


## Source references

- [_parse_shared_strings](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/runner.py#L320)
- [_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L635)
