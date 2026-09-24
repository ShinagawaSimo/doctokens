# Rich text runs

[XLSX](../README.md) / Rich text runs

Shared-string run formatting is preserved in semantic output.

## Processing

Retain all runs only when at least one has formatting. Wrapper order is hyperlink, bold, italic, underline, color. Rich-value display can take precedence over these runs.

## Fields

### `text`

- **Output**
  - Run character data inside cell.

- **OOXML**
  - s:si/s:r/s:t.

- **IR**
  - `RichTextRun.text: str`

- **Parsing**
  - Copy direct t or empty string. Inline strings are not aggregated through this path.

### `bold`

- **Output**
  - Nested b wrapper.

- **OOXML**
  - s:rPr/s:b.

- **IR**
  - `bool`

- **Parsing**
  - Element presence → true; source val=false is not interpreted.

### `italic`

- **Output**
  - Nested i wrapper.

- **OOXML**
  - s:rPr/s:i.

- **IR**
  - `bool`

- **Parsing**
  - Element presence → true.

### `underline`

- **Output**
  - Nested u wrapper.

- **OOXML**
  - s:rPr/s:u.

- **IR**
  - `bool`

- **Parsing**
  - Element presence → true; underline styles are collapsed.

### `color`

- **Output**
  - Nested color/@value.

- **OOXML**
  - s:rPr/s:color/@rgb.

- **IR**
  - `str`

- **Parsing**
  - Skip empty or 00000000; strip first 2 characters from 8-character values; add #. No theme/indexed/tint resolution on rich runs.


## Source references

- [_parse_shared_strings](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/runner.py#L320)
- [_append_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L382)
