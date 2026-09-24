# Text emphasis

[PPTX](../README.md) / Text emphasis

Semantic DTX nests wrappers in the order color, underline, italic, bold, hyperlink.

## Processing

Semantic/session inheritance: master and layout style → shape role/type/idx → txBody lstStyle → paragraph defRPr → run rPr. Merge direct dictionaries in that order. Plain/structural one-shot parsing omits formatting/theme resolution.

## Fields

### `bold`

- **Output**
  - `<b>...</b>`.

- **OOXML**
  - a:rPr/@b or child a:b.

- **IR**
  - `Run.format.bold: bool`

- **Parsing**
  - Present attribute → lower-case value outside 0/false/off/no is true; otherwise child presence true. False overrides inherited true.

### `italic`

- **Output**
  - `<i>...</i>`.

- **OOXML**
  - a:rPr/@i or child a:i.

- **IR**
  - `Run.format.italic: bool`

- **Parsing**
  - Same boolean rule as bold.

### `underline`

- **Output**
  - `<u>...</u>`.

- **OOXML**
  - a:rPr/@u or child a:u/@val.

- **IR**
  - `Run.format.underline: bool`

- **Parsing**
  - False for exact none/0/false/off; present other value true. Child missing val also true.

### `color`

- **Output**
  - `<color value="#RRGGBB">...</color>`.

- **OOXML**
  - a:rPr/a:solidFill color child.

- **IR**
  - `Run.format.color: str`

- **Parsing**
  - First resolved non-default color; see [colors](color.md). Near-black direct colors are omitted rather than explicitly clearing inherited colors.


## Source references

- [SlideParser._shape_text_styles](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L405)
- [_format_properties](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L1046)
- [_append_shape_text](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L151)
