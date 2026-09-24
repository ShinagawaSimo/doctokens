# Endnote references

[DOCX](../README.md) / Endnote references

A `endnote` reference is an inline object attached to its containing run.

## Fields

### `type`

- **Output**
  - `<endnote-ref id="2"/>`; DTP `[ed2]`.

- **OOXML**
  - `w:r/w:endnoteReference`

- **IR**
  - `InlineObject.type: str`

- **Parsing**
  - Assign `"endnoteRef"`. In a mixed run, serialized run text precedes its inline objects.

### `id`

- **Output**
  - `endnote-ref/@id`; DTP marker suffix.

- **OOXML**
  - `w:endnoteReference/@w:id`

- **IR**
  - `InlineObject.id: str | None`

- **Parsing**
  - Copy without integer conversion or referential validation.

- **Absence and defaults**
  - Absent: `None`; omit the DTX attribute and use an empty DTP suffix.

- **Diagnostics**
  - No warning is emitted solely for an absent ID or an unresolved note/comment.


## Source references

- [RunParser._handle_child](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L107)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L167)
- [plain_object_placeholder](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/plain/helpers.py#L89)
