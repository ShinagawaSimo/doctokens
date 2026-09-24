# Content controls

[DOCX](../README.md) / Content controls

A control supplies metadata around its saved content; it does not perform binding or interaction.

## Fields

### `type`

- **Output**
  - `content-control/@type`.

- **OOXML**
  - Recognized local child name of `w:sdtPr`.

- **IR**
  - `ContentControl.controlType: str`

- **Parsing**
  - Map text/richText/picture/date/comboBox/dropDownList/checkbox/group/repeatingSection/citation; docPartList/docPartObj → buildingBlock. Last recognized type wins.

- **Absence and defaults**
  - `unknown`.

### `label`

- **Output**
  - `content-control/@label` in both XML densities.

- **OOXML**
  - `w:alias/@w:val`, then `w:tag/@w:val`.

- **IR**
  - `ContentControl.alias`, `ContentControl.tag`

- **Parsing**
  - `alias or tag`; omit if empty.

### `id`

- **Output**
  - Internal source identifier.

- **OOXML**
  - `w:id/@w:val`

- **IR**
  - `ContentControl.id: str`

- **Parsing**
  - Copy nonempty value; no current DTX ID attribute.

### `tag`

- **Output**
  - Semantic `@tag`.

- **OOXML**
  - `w:tag/@w:val`

- **IR**
  - `ContentControl.tag: str`

- **Parsing**
  - Emit only if nonempty and different from label.

### `lock`

- **Output**
  - Semantic `@lock`; structural `locked="true"` for sdtLocked/contentLocked.

- **OOXML**
  - `w:lock/@w:val`

- **IR**
  - `ContentControl.lock: str`

- **Parsing**
  - Copy nonempty value; does not enforce document editing protection.

### `placeholder`

- **Output**
  - Semantic `@placeholder`.

- **OOXML**
  - `w:placeholder/w:docPart/@w:val`

- **IR**
  - `ContentControl.placeholder: str`

- **Parsing**
  - Copy nonempty value.

### `binding`

- **Output**
  - Semantic `@binding` containing XPath.

- **OOXML**
  - `w:dataBinding/@w:xpath`, `@w:storeItemID`, `@w:prefixMappings`

- **IR**
  - `ContentControl.binding: dict[str,str]`

- **Parsing**
  - Retain nonempty keys; output only `xpath`. See [binding fields](control-binding.md).

### `choices`

- **Output**
  - `@choices="A|B=value"` in both XML densities.

- **OOXML**
  - comboBox/dropDownList child listItem.

- **IR**
  - `ContentControl.options: list[ContentControlOption]`

- **Parsing**
  - Preserve source order; join nonempty display/value summaries with `|`.

### `display`

- **Output**
  - Choice display text.

- **OOXML**
  - `w:listItem/@w:displayText`

- **IR**
  - `ContentControlOption.display: str`

- **Parsing**
  - If empty, use value.

### `value`

- **Output**
  - Choice `=value` suffix only when different from display.

- **OOXML**
  - `w:listItem/@w:value`

- **IR**
  - `ContentControlOption.value: str`

- **Parsing**
  - If empty, use display; omit item if both empty.

### `checked`

- **Output**
  - Semantic `@checked="true|false"`.

- **OOXML**
  - Local attribute `checked` on the checkbox type node.

- **IR**
  - `ContentControl.checked: bool`

- **Parsing**
  - Lowercase value outside `0/false/off/none` is true.

- **Absence and defaults**
  - Absent attribute: no member.

- **Notes**
  - The current extractor does not read the usual nested checkbox/checked element; that source form does not populate this field.

### `date-format`

- **Output**
  - Semantic `@date-format`.

- **OOXML**
  - `w:date/w:dateFormat/@w:val`

- **IR**
  - `ContentControl.dateFormat: str`

- **Parsing**
  - Copy nonempty format string; no date computation.

### `multiLine`

- **Output**
  - No public attribute.

- **OOXML**
  - `w:text/@w:multiLine`

- **IR**
  - Declared `ContentControl.multiLine: bool`

- **Parsing**
  - Current parser handles text in its earlier type branch and continues, so the later multiLine branch is unreachable.

- **Absence and defaults**
  - Not populated by that source path.

### `temporary`

- **Output**
  - No public attribute.

- **OOXML**
  - `w:temporary/@w:val`

- **IR**
  - `ContentControl.temporary: bool`

- **Parsing**
  - Current bool helper returns false for absent val and false tokens; no editing action.


## Source references

- [parse_content_control](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/content_controls.py#L28)
- [_parse_options](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/content_controls.py#L97)
- [_append_controls](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L350)
