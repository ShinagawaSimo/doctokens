# Paragraph borders

[DOCX](../README.md) / Paragraph borders

Border properties are extracted for semantic formatting.

## Fields

### `side`

- **Output**
  - Semantic `border-top`, `border-left`, `border-bottom`, `border-right`, `border-between`, `border-bar`.

- **OOXML**
  - `w:pPr/w:pBdr/w:{side}`

- **IR**
  - `ParagraphBlock.borders: dict[str, ParagraphBorder]`

- **Parsing**
  - Merge document defaults, table/paragraph style sides, and direct sides. Explicit nil/none clears the inherited side; remove cleared sides only at final visible projection.

- **Absence and defaults**
  - No parsed borders: no attributes.

### `style`

- **Output**
  - First component of `border-{side}`.

- **OOXML**
  - `@w:val`

- **IR**
  - `ParagraphBorder.style: str`

- **Parsing**
  - Lowercase; omit an empty source value. Preserve nil/none as internal cancellation values during inheritance. Renderer default for an existing visible record without style is `single`.

### `color`

- **Output**
  - `border-{side}="style:#RRGGBB"`.

- **OOXML**
  - `@w:color`

- **IR**
  - `ParagraphBorder.color: str`

- **Parsing**
  - Normalize supported hex; append only if nonempty.

- **Absence and defaults**
  - No color suffix.

### `size`

- **Output**
  - No main-text attribute.

- **OOXML**
  - `@w:sz`

- **IR**
  - `ParagraphBorder.size: str`

- **Parsing**
  - Retain nonempty source string; not used for page layout.
