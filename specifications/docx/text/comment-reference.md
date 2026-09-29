# Comment references

[DOCX](../README.md) / Comment references

A `comment` reference is an inline object attached to its containing run.

## Fields

### `type`

- **Output**
  - `<comment-ref id="2"/>`; DTP `[cmt2]`.

- **OOXML**
  - `w:r/w:commentReference`

- **IR**
  - `InlineObject.type: str`

- **Parsing**
  - Assign `"commentRef"`. In a mixed run, serialized run text precedes its inline objects.

### `id`

- **Output**
  - `comment-ref/@id`; DTP marker suffix.

- **OOXML**
  - `w:commentReference/@w:id`

- **IR**
  - `InlineObject.id: str | None`

- **Parsing**
  - Copy without integer conversion or referential validation. The first block associated with a string ID becomes the comment anchor.

- **Absence and defaults**
  - Absent: `None`; omit the DTX attribute and use an empty DTP suffix.

- **Diagnostics**
  - No warning is emitted solely for an absent ID or an unresolved note/comment.


## Source references

- [RunParser._handle_child](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L107)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L164)
- [plain_object_placeholder](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/plain/helpers.py#L89)
