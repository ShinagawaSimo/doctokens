# Rich text runs

[XLSX](../README.md) / Rich text runs

Shared-string and inline-string run formatting use the same parser and semantic projection.

## Processing

Retain all runs only when at least one has an explicit supported property, including an explicit false. Wrapper order is hyperlink, an optional run reset, bold, italic, underline, color. Rich-value display can take precedence over these runs. Lower densities retain the same decoded concatenated reading text without emphasis wrappers.

## Fields

### `text`

- **Output**
  - Run character data inside cell.

- **OOXML**
  - Shared s:si/s:r/s:t or inline s:is/s:r/s:t.

- **IR**
  - `RichTextRun.text: str`

- **Parsing**
  - Decode one ST_Xstring layer in each t, then concatenate in source order. Phonetic guides do not duplicate cell text. Text number-format sections receive decoded text and preserve rich runs when inserting source text.

### `bold`

- **Output**
  - Nested b wrapper.

- **OOXML**
  - s:rPr/s:b.

- **IR**
  - `bool`

- **Parsing**
  - Absent: inherit the cell's effective font. Present without val: true. Explicit 0/false/off: false. A false value emits `<run bold="false">` only when it clears a bold cell/style-range context; otherwise it adds no output noise.

### `italic`

- **Output**
  - Nested i wrapper.

- **OOXML**
  - s:rPr/s:i.

- **IR**
  - `bool`

- **Parsing**
  - Same on/off and inherited-reset rules as bold, using an italic=false run attribute when necessary.

### `underline`

- **Output**
  - Nested u wrapper.

- **OOXML**
  - s:rPr/s:u.

- **IR**
  - `bool`

- **Parsing**
  - Present without val: single underline. Values 0/false/off/none disable it; other underline styles collapse to one u wrapper. An underline=false run attribute clears an inherited underline only when needed.

### `color`

- **Output**
  - Nested color/@value.

- **OOXML**
  - s:rPr/s:color/@rgb.

- **IR**
  - `str`

- **Parsing**
  - Skip empty or 00000000; strip first 2 characters from 8-character values; add #. No theme/indexed/tint resolution on rich runs.

## Examples

- Inline `<is><r><t>Hello</t></r><r><rPr><b/></rPr><t>World</t></r></is>` reads `HelloWorld`; semantic emits `Hello<b>World</b>`.
- An inherited bold cell with an explicitly disabled rich run emits `<cell bold="true"><run bold="false">Plain</run></cell>`; a false source property does not incorrectly create a bold wrapper.
