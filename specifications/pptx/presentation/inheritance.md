# Layout and master inheritance

[PPTX](../README.md) / Layout and master inheritance

The semantic parse plan and sessions resolve template defaults. Template prompt text is not copied into slide content.

## Fields

### `theme`

- **Output**
  - Input to [color resolution](../text/color.md).

- **OOXML**
  - Slide → layout → master → theme relationships.

- **IR**
  - `LayoutContext.theme: dict[str, str]`

- **Parsing**
  - Use the master’s [theme](theme.md); missing master uses the deck theme.

### `placeholders`

- **Output**
  - Input to [placeholder identity](../shapes/placeholder.md) and geometry.

- **OOXML**
  - Direct `p:sp` children of template `p:cSld/p:spTree`, descendant `p:ph`.

- **IR**
  - `LayoutContext.placeholders: dict[str, PlaceholderInfo]`

- **Parsing**
  - Layout keys use `@idx` (default `"0"`); the first layout placeholder of a type also provides `type:{type}`. Type defaults to `"obj"`. Master keys use type, with later occurrences replacing earlier ones. Layout geometry falls back to master geometry of the same type.

- **Absence and defaults**
  - Missing templates: empty placeholder map.

### `color_map`

- **Output**
  - Maps scheme names to [theme slots](theme.md#slots).

- **OOXML**
  - Master/layout `p:clrMap`; slide `p:clrMapOvr/a:overrideClrMapping`, then `a:masterClrMapping`, or `p:clrMap`.

- **IR**
  - `LayoutContext.color_map: dict[str, str]`

- **Parsing**
  - Overlay in order: default map, master map, layout map, slide map. Read present attributes `tx1`, `tx2`, `bg1`, `bg2`, `accent1`–`accent6`, `hlink`, `folHlink`; retain empty strings. Defaults: `tx1=dk1`, `tx2=dk2`, `bg1=lt1`, `bg2=lt2`; accent and hyperlink names map to themselves.

### `text_styles`

- **Output**
  - Paragraph and run defaults.

- **OOXML**
  - `p:txStyles` children `titleStyle`, `bodyStyle`, `otherStyle`; placeholder `p:txBody/a:lstStyle`.

- **IR**
  - `LayoutContext.text_styles: dict[str, dict[int, ParagraphStyle]]`

- **Parsing**
  - Role keys are `title`, `body`, `other`; placeholder styles use `idx:{idx}` and `type:{type}`. `defPPr` uses level 0; `lvlNpPr` uses `max(0, int(N)-1)`, invalid N is skipped. Read bullet, auto-numbering, and `defRPr` defaults. Merge layout over master by key and level; merge `runFormat` member by member. Subsequent slide-level precedence is defined in [text emphasis](../text/emphasis.md).

- **Absence and defaults**
  - Missing styles: `{}`.

- **Diagnostics**
  - `LAYOUT_PART_MISSING` or `LAYOUT_XML_INVALID`: deck theme, default color map, empty placeholder/style maps. `MASTER_PART_MISSING` or `MASTER_XML_INVALID`: keep layout parsing with empty master placeholders/styles and deck theme.


## Source references

- [LayoutMasterResolver.resolve](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L109)
- [LayoutMasterResolver._layout_model](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L145)
- [LayoutMasterResolver._text_styles](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L260)
- [LayoutMasterResolver._merge_text_styles](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L357)
