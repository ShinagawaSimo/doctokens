# Automatic numbering

[DOCX](../README.md) / Automatic numbering

Counters are scoped by numbering instance and advanced while parsing source paragraphs.

## Processing

1. Resolve direct/style numId and level.
2. In `original` revision view, apply parsed `w:numberingChange/@w:original` level overrides when available.
3. Resolve the level definition. Missing level produces a warning and no label.
4. Increment its counter. A deeper level with `restart_level == 0` never resets. Otherwise its restart boundary is `deeper_level - 1` by default or `restart_level - 1`; reset when the used level is at or above that boundary.
5. Render the marker and suffix; insert the resulting synthetic run before original runs.

## Fields

### `numId`

- **Output**
  - Internal instance key.

- **OOXML**
  - Direct `w:numPr/w:numId/@w:val`, then style numbering.

- **IR**
  - `NumberingLabel.numId: str`

- **Parsing**
  - Direct `"0"` disables numbering. Otherwise direct ID wins, then style ID.

- **Absence and defaults**
  - No ID: no numbering.

### `level`

- **Output**
  - Internal level key.

- **OOXML**
  - `w:ilvl/@w:val` or style binding.

- **IR**
  - `NumberingLabel.level: int`

- **Parsing**
  - Parse int; fall back through style level-for-style, style level, then 0.

- **Diagnostics**
  - Malformed integer: `INVALID_PARAGRAPH_NUMBERING_LEVEL`, fallback 0. Unresolved level: `NUMBERING_LEVEL_MISSING`, no label.

### `counter`

- **Output**
  - Contributes to visible marker.

- **OOXML**
  - `w:start/@w:val`, instance overrides, preceding paragraphs.

- **IR**
  - `NumberingLabel.counter: int`

- **Parsing**
  - `counters[level] = counters.get(level, start - 1) + 1`; then reset eligible deeper levels. State advances before an empty paragraph is discarded.

### `format`

- **Output**
  - Controls label characters.

- **OOXML**
  - `w:lvl/w:numFmt/@w:val`

- **IR**
  - `NumberingLabel.format: str`

- **Parsing**
  - Use resolved number format; `none` and picture bullets have empty textual marker.

- **Diagnostics**
  - Format-specific diagnostics include `UNSUPPORTED_NUMBER_FORMAT`, `APPLICATION_DEFINED_NUMBER_FORMAT`, `NUMBERING_VALUE_OUT_OF_RANGE`; the formatter defines their actual fallback.

### `template`

- **Output**
  - Internal label template.

- **OOXML**
  - `w:lvlText/@w:val`

- **IR**
  - `str | None`

- **Parsing**
  - Expand `%%|%([1-9][0-9]*)`: `%%` becomes `%`; `%N` uses zero-based level `N-1`. Missing referenced levels use the current definition; absent counters use the referenced start. A referenced `none` format yields `""`. Without a template, ordinary bullets yield `•`; other formats convert the current counter. Legal bullets use a decimal counter. See [level definitions](numbering-level.md) and [number conversion](number-format.md).

### `suffix`

- **Output**
  - Spacing after marker.

- **OOXML**
  - `w:suff/@w:val`

- **IR**
  - `NumberingLabel.suffix: str`

- **Parsing**
  - `nothing` → `""`; `space` → `" "`; all other values → `"\t"`.

### `label`

- **Output**
  - Visible marker without suffix.

- **OOXML**
  - Resolved template/format/counters.

- **IR**
  - `NumberingLabel.label: str`

- **Parsing**
  - Format level placeholders; bullet-symbol conversion applies to bullet templates.

### `text`

- **Output**
  - Synthetic numbering run prefix only.

- **OOXML**
  - `label`, suffix, picture/none status.

- **IR**
  - `NumberingLabel.text: str`

- **Parsing**
  - `""` for `none` or picture bullet; otherwise `label + suffix_text`. Does not include paragraph body text.

### `markerFormat`

- **Output**
  - Semantic formatting on the synthetic marker run.

- **OOXML**
  - Level `w:rPr`.

- **IR**
  - `dict[str, bool | str | None]`

- **Parsing**
  - Store `level.marker_format` in every resolved label. The synthetic run copies it only when character formatting is enabled.

### `markerFont`

- **Output**
  - Internal symbol-font context; no DTX font attribute.

- **OOXML**
  - Level font declaration.

- **IR**
  - Optional `str`

- **Parsing**
  - Keep nonempty marker font.

### `pictureBulletId`

- **Output**
  - Internal picture-bullet lookup.

- **OOXML**
  - `w:lvlPicBulletId/@w:val`

- **IR**
  - `str | None`

- **Parsing**
  - Resolve numbered picture relationship from `word/numbering.xml`.

### `markerImageId`

- **Output**
  - Image object resource association.

- **OOXML**
  - Resolved picture-bullet asset.

- **IR**
  - `str | None`

- **Parsing**
  - If asset exists, replace marker run with one space and an image object with alt `Picture bullet`.

- **Absence and defaults**
  - Initially `None`; unresolved asset leaves no image object.

### `legal`

- **Output**
  - Changes placeholder number format.

- **OOXML**
  - `w:isLgl`

- **IR**
  - `bool`

- **Parsing**
  - Legal numbering uses decimal formatting for referenced levels.


## Source references

- [ParagraphNumbering.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/numbering.py#L39)
- [NumberingState](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/state.py#L15)
- [NumberFormatRenderer](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L32)
- [NumberingParser](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/parser.py#L97)
