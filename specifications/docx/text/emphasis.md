# Emphasis and color

[DOCX](../README.md) / Emphasis and color

Only semantic DTX emits reading-format wrappers.

## Processing

Wrapper order, outer to inner: enclosing revisions in source order, citation, hyperlink, mark, color, strike, underline, italic, bold, superscript, subscript, small-caps, then ruby around its own base runs. Only present/truthy properties participate.

Resolved style properties retain explicit false/clear values until final visible projection. Document defaults and independently resolved table/paragraph/character layers follow the [style cascade](style.md); linked-style IDs do not add an implicit layer. Numbering markers use the same visible-format filtering. Historical run property sets are selected by [revision view](revision.md).

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
  - Sets superscript true and subscript false. Both values survive inheritance merging. `baseline` explicitly clears both.

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
  - Sets subscript true and superscript false. Both values survive inheritance merging. `baseline` explicitly clears both.

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
  - Normalize valid literal hex. Keep black/near-black during inheritance so they can override an earlier color; omit them only after effective run resolution. Default-like colors are black or hex colors whose maximum component is <=48 and component spread is <=16.
  - Explicit `auto` clears an inherited literal without guessing a theme/system color. Missing color leaves inheritance unchanged; source theme-only colors do not imply full Word theme resolution.
  - Example: red paragraph style plus direct black produces ordinary text; direct green produces `<color value="#00AA00">text</color>`.

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
  - Normalize background fill; preferred over highlight. Explicit `fill="auto"` or shading `val="nil"` clears an inherited background before the visible projection.

- **Absence and defaults**
  - Absent/disabled: no wrapper.
