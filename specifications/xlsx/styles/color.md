# Spreadsheet colors

[XLSX](../README.md) / Spreadsheet colors

Cell fonts and fills use the workbook theme when necessary.

## Fields

### `rgb`

- **Output**
  - #RRGGBB-style output string.

- **OOXML**
  - color/@rgb.

- **IR**
  - Resolved string.

- **Parsing**
  - Nonempty and not 00000000 wins; length 8 → remove first 2 characters; otherwise keep as supplied. This helper does not enforce six hex digits.

### `theme`

- **Output**
  - Resolved theme color.

- **OOXML**
  - color/@theme.

- **IR**
  - Integer theme index.

- **Parsing**
  - Slots0..11:lt1,dk1,lt2,dk2,accent1..6,hlink,folHlink. Read xl/theme/theme1.xml; missing theme/scheme → Office default palette.

### `tint`

- **Output**
  - Adjusted theme color.

- **OOXML**
  - color/@tint.

- **IR**
  - float.

- **Parsing**
  - Applies only to theme branch. Negative: int(c*(1+tint)); positive: int(c*(1-tint)+255*tint); clamp0..255. ValueError → base color.

### `indexed`

- **Output**
  - No resolved color.

- **OOXML**
  - color/@indexed.

- **IR**
  - Not retained.

- **Parsing**
  - Indexed palette colors are not resolved in this path.


## Source references

- [_resolve_color](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L434)
- [_parse_theme](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L393)
- [_apply_tint](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L467)
