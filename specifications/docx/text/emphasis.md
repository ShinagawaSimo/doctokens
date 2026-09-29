# Emphasis and color

[DOCX](../README.md) / Emphasis and color

Only semantic DTX emits reading-format wrappers.

## Processing

Wrapper order, outer to inner: revision, citation, hyperlink, mark, color, strike, underline, italic, bold, superscript, subscript, small-caps. Only present/truthy properties participate.

## Fields

### `bold`

- **Output**
  - Semantic `<b>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:b`

- **IR**
  - `Run.format["bold"]`

- **Parsing**
  - Word on/off parsing.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `italic`

- **Output**
  - Semantic `<i>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:i`

- **IR**
  - `Run.format["italic"]`

- **Parsing**
  - Word on/off parsing.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `underline`

- **Output**
  - Semantic `<u>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:u`

- **IR**
  - `Run.format["underline"]`

- **Parsing**
  - Missing val → single; false for `0/false/off/none`; line style is not preserved.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `strike`

- **Output**
  - Semantic `<s>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:strike, w:dstrike`

- **IR**
  - `Run.format["strike"]`

- **Parsing**
  - Double-strike overrides strike when both present; both map to s.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `superscript`

- **Output**
  - Semantic `<sup>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:vertAlign[@w:val="superscript"]`

- **IR**
  - `Run.format["superscript"]`

- **Parsing**
  - Sets superscript and removes subscript in the same direct format.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `subscript`

- **Output**
  - Semantic `<sub>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:vertAlign[@w:val="subscript"]`

- **IR**
  - `Run.format["subscript"]`

- **Parsing**
  - Sets subscript and removes superscript in the same direct format.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `smallCaps`

- **Output**
  - Semantic `<small-caps>`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:smallCaps`

- **IR**
  - `Run.format["smallCaps"]`

- **Parsing**
  - Word on/off parsing.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `color`

- **Output**
  - Semantic `<color value="#RRGGBB">`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:color/@w:val`

- **IR**
  - `Run.format["color"]`

- **Parsing**
  - Normalize valid literal hex; source theme-only colors do not imply full Word theme resolution.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `highlight`

- **Output**
  - Semantic `<mark value="...">`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:highlight/@w:val`

- **IR**
  - `Run.format["highlight"]`

- **Parsing**
  - Named highlight mapping; background takes precedence when both exist.

- **Absence and defaults**
  - Absent/disabled: no wrapper.

### `bg`

- **Output**
  - Semantic `<mark value="...">`; omitted in structural/plain.

- **OOXML**
  - `w:rPr/w:shd/@w:fill`

- **IR**
  - `Run.format["bg"]`

- **Parsing**
  - Normalize background fill; preferred over highlight.

- **Absence and defaults**
  - Absent/disabled: no wrapper.


## Source references

- [parse_run_format](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/formatting.py#L26)
- [merge_run_formats](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/formatting.py#L90)
- [_append_format_wrappers](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L141)
