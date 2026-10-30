# Comment mentions

[XLSX](../README.md) / Comment mentions

Explicitly mentioned people add reading information independently of the
comment author. Mention locations are not an editable text-range projection.

## Fields

### `person`

- **Output**
  - Semantic `comment/mention/@person`. Plain/structural omit mention metadata.
- **OOXML**
  - mention/@personId resolved through the workbook people catalog.
- **IR**
  - `AnnotationMention.person: str`.
- **Parsing**
  - Retain distinct nonempty display names in source mention order.
  - Skip a mention whose person cannot resolve; preserve the comment text.
  - Raw person IDs, startIndex and length are not retained or emitted. No
    unvalidated offset is presented as an exact range in the readable comment.
