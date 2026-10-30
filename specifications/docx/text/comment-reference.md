# Comment references

[DOCX](../README.md) / Comment references

A `comment` reference is an inline object attached to its containing run.

## Fields

### `type`

- **Output**
  - `<comment-ref id="2"/>` in structural/semantic. Plain omits the ID reference and retains comment text/status in its Comments section.

- **OOXML**
  - `w:r/w:commentReference`

- **IR**
  - `InlineObject.type: str`

- **Parsing**
  - Assign `"commentRef"`. In a mixed run, serialized run text precedes its inline objects.

### `id`

- **Output**
  - `comment-ref/@id` in structural/semantic.

- **OOXML**
  - `w:commentReference/@w:id`

- **IR**
  - `InlineObject.id: str | None`

- **Parsing**
  - Copy without integer conversion or referential validation. The first associated block is retained internally for selecting related comments; its internal ID is not emitted as a public anchor.

- **Absence and defaults**
  - Absent: `None`; omit the DTX attribute.

- **Diagnostics**
  - No warning is emitted solely for an absent ID or an unresolved note/comment.
