# Placeholders

[PPTX](../README.md) / Placeholders

Placeholder type supplies title identity and inherited defaults.

## Fields

### `placeholderType`

- **Output**
  - Text `title` for title/ctrTitle; otherwise p. Semantic @placeholder; structural text also emits @placeholder.

- **OOXML**
  - p:ph/@type and @idx.

- **IR**
  - `ShapeBlock.placeholderType: str`

- **Parsing**
  - Direct nonempty type wins. Otherwise semantic/session resolves layout by idx (default 0), then by own type; take inherited type.

- **Absence and defaults**
  - No placeholder attribute.

### `idx`

- **Output**
  - Internal lookup key.

- **OOXML**
  - p:ph/@idx.

- **IR**
  - LayoutContext.placeholders key.

- **Parsing**
  - Default "0". Layout placeholders can inherit master geometry by type; template text is not inserted into slide content.


## Source references

- [SlideGeometry._attach_inheritance](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/geometry.py#L109)
- [LayoutMasterResolver._layout_model](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L146)
