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
  - Merge inherited sides then direct sides. Empty/nil/none direct borders are discarded by extraction, so they do not explicitly clear an inherited side.

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
  - Lowercase; omit source values `""`, `nil`, `none`. Renderer default for an existing record without style is `single`.

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


## Source references

- [parse_paragraph_borders](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/formatting.py#L55)
- [merge_paragraph_borders](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/formatting.py#L81)
- [_add_semantic_block_attrs](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L88)
