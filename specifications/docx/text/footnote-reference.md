# Footnote references

[DOCX](../README.md) / Footnote references

A `footnote` reference is an inline object attached to its containing run.

## Fields

### `type`

- **Output**
  - `<footnote-ref id="2"/>`; DTP `[fn2]`.

- **OOXML**
  - `w:r/w:footnoteReference`

- **IR**
  - `InlineObject.type: str`

- **Parsing**
  - Assign `"footnoteRef"`. In a mixed run, serialized run text precedes its inline objects.

### `id`

- **Output**
  - `footnote-ref/@id`; DTP marker suffix.

- **OOXML**
  - `w:footnoteReference/@w:id`

- **IR**
  - `InlineObject.id: str | None`

- **Parsing**
  - Copy without integer conversion or referential validation.

- **Absence and defaults**
  - Absent: `None`; omit the DTX attribute and use an empty DTP suffix.

- **Diagnostics**
  - No warning is emitted solely for an absent ID or an unresolved note/comment.
