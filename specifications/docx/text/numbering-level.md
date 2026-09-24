# Numbering levels

[DOCX](../README.md) / Numbering levels

A `NumberingLevel` defines one zero-based level. It is read from `word/numbering.xml`; [numbering instances](numbering-instance.md) select and override it.

## Fields

### `numbering_level`

- **Output**
  - Index used by [automatic numbering](numbering.md).

- **OOXML**
  - `w:lvl/@w:ilvl`

- **IR**
  - `NumberingLevel.numbering_level: int`

- **Parsing**
  - `int(value)`; an instance override replaces it with `w:lvlOverride/@w:ilvl`.

- **Absence and defaults**
  - Missing or invalid: `0`.

### `start`

- **Output**
  - Initial counter value.

- **OOXML**
  - `w:lvl/w:start/@w:val`

- **IR**
  - `NumberingLevel.start: int`

- **Parsing**
  - `int(value)`; a resolved instance start override takes precedence.

- **Absence and defaults**
  - Missing or invalid: `1`.

### `number_format`

- **Output**
  - Visible counter representation.

- **OOXML**
  - `w:lvl/w:numFmt/@w:val`

- **IR**
  - `NumberingLevel.number_format: str`

- **Parsing**
  - Read the first `w:numFmt`; see [number formats](number-format.md).

- **Absence and defaults**
  - Absent or empty: `"decimal"`.

### `level_text`

- **Output**
  - Marker template.

- **OOXML**
  - `w:lvl/w:lvlText/@w:val`

- **IR**
  - `NumberingLevel.level_text: str | None`

- **Parsing**
  - Preserve the attribute, including an empty value. Expansion is defined by [automatic numbering](numbering.md#template).

- **Absence and defaults**
  - Absent: `None`.

### `suffix`

- **Output**
  - Characters following the marker.

- **OOXML**
  - `w:lvl/w:suff/@w:val`

- **IR**
  - `NumberingLevel.suffix: str`

- **Parsing**
  - `"nothing"` → `""`; `"space"` → `" "`; all other values → `"\t"`.

- **Absence and defaults**
  - Absent or empty: `"tab"`.

### `paragraph_style_id`

- **Output**
  - Style-to-level association; no output attribute.

- **OOXML**
  - `w:lvl/w:pStyle/@w:val`

- **IR**
  - `NumberingLevel.paragraph_style_id: str | None`

- **Parsing**
  - Copy the attribute. `NumberingMap.level_for_style()` checks instance overrides in insertion order, then sorted base level indices, then linked instances.

- **Absence and defaults**
  - Absent: `None`.

### `marker_format`

- **Output**
  - Semantic emphasis on the synthetic marker run.

- **OOXML**
  - `w:lvl/w:rPr`

- **IR**
  - `NumberingLevel.marker_format: RunFormat`

- **Parsing**
  - Apply [run formatting](emphasis.md). The label retains the result; application to the synthetic run requires the character-format feature.

- **Absence and defaults**
  - Absent: `{}`.

### `marker_font`

- **Output**
  - Context for converting private-use bullet characters; no font attribute.

- **OOXML**
  - `w:lvl/w:rPr/w:rFonts/@w:ascii`, `@w:hAnsi`, `@w:eastAsia`, `@w:cs`

- **IR**
  - `NumberingLevel.marker_font: str | None`

- **Parsing**
  - First nonempty attribute in the stated order. See [bullet symbols](bullet-symbol.md).

- **Absence and defaults**
  - No nonempty value: `None`.

### `picture_bullet_id`

- **Output**
  - Image marker lookup; textual marker is empty when this value is truthy.

- **OOXML**
  - `w:lvl/w:lvlPicBulletId/@w:val`

- **IR**
  - `NumberingLevel.picture_bullet_id: str | None`

- **Parsing**
  - Look up the matching `w:numPicBullet/@w:numPicBulletId`; use its first descendant `v:imagedata` with a nonempty `r:id`. Resolve against `word/numbering.xml` relationships.

- **Absence and defaults**
  - Absent: `None`.

### `restart_level`

- **Output**
  - Counter reset boundary.

- **OOXML**
  - `w:lvl/w:lvlRestart/@w:val`

- **IR**
  - `NumberingLevel.restart_level: int | None`

- **Parsing**
  - `0`: never reset. Otherwise reset after a used level `<= restart_level - 1`. With `None`, use `numbering_level - 1`. Nested instance level overrides reset this member to `None`.

- **Absence and defaults**
  - Missing or invalid: `None`.

### `is_legal`

- **Output**
  - Decimal placeholders in the current marker.

- **OOXML**
  - `w:lvl/w:isLgl/@w:val`

- **IR**
  - `NumberingLevel.is_legal: bool`

- **Parsing**
  - Word on/off parsing: present element without a value is on. A legal bullet uses its decimal counter instead of the bullet template.

- **Absence and defaults**
  - Missing element: `False`.

### `language`

- **Output**
  - Language input to [number conversion](number-format.md#language).

- **OOXML**
  - `w:lvl/w:rPr/w:lang/@w:val`, then `@w:eastAsia`

- **IR**
  - `NumberingLevel.language: str | None`

- **Parsing**
  - Use the first truthy value; preserve it for the formatter.

- **Absence and defaults**
  - Absent: `None`.

### `custom_format`

- **Output**
  - Custom number-format pattern.

- **OOXML**
  - `w:lvl/w:numFmt/@w:format`

- **IR**
  - `NumberingLevel.custom_format: str | None`

- **Parsing**
  - Copy without validation; evaluated by [number conversion](number-format.md#custom_format).

- **Absence and defaults**
  - Absent: `None`.


## Source references

- [NumberingLevel](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/models.py#L13)
- [NumberingParser._parse_level](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/parser.py#L159)
- [NumberingMap.level_for_style](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/parser.py#L71)
