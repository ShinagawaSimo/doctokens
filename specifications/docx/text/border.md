# Paragraph borders

[DOCX](../README.md) / Paragraph borders

Border side/style/color are semantic reading clues. Structural/plain never
serialize border metadata, including after a richer session read. Exact line
width and page geometry are outside this projection.

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
  - Lowercase; omit an empty source value. Preserve nil/none as internal
    cancellation values during inheritance. Every retained visible record has
    a saved style; the renderer does not fabricate single for a missing style.

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
