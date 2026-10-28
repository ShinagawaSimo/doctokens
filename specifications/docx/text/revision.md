# Revisions

[DOCX](../README.md) / Revisions

The selected view determines which saved inline revision content participates in output. This does not reconstruct historical paragraph marks, table-row revisions, or historical property sets.

## Fields

### `revision_mode`

- **Output**
  - DTX root `revision-view`; DTP header `revision_view`.

- **OOXML**
  - Call option.

- **IR**
  - `ParseOptions.revision_mode = "final"`

- **Parsing**
  - `final`: include ins/moveTo; omit del/moveFrom. `original`: inverse. `review`: include both.
  - Selected wrappers traverse the ordinary inline parser, preserving `t` and selected `delText`, tabs, breaks, special characters, ruby, links, controls, images, text boxes, and mathematical objects in source order. Deleted field instructions can annotate cached results; they never become display text.
  - Body paragraphs, table-cell paragraphs, text-box stories, and parsed ancillary paragraphs use the same inline visibility policy. An omitted wrapper contributes no page breaks or inline objects.

- **Diagnostics**
  - Invalid enum: `ValueError`.

### `revisions`

- **Output**
  - Semantic `<ins>`, `<del>`, `<move-from>`, or `<move-to>`, wrapping both text and objects. Nested revisions nest in source order, outermost first.
  - Plain/structural retain the selected text and objects without review wrappers.

- **OOXML**
  - `w:ins/w:moveTo/w:del/w:moveFrom`

- **IR**
  - `Run.revisions: list[Revision]`, populated only for review.
  - Each `Revision` has `kind: "inserted" | "deleted" | "moved-from" | "moved-to"`, `author`, `date`, and `moveName`.

- **Parsing**
  - Preserve all enclosing selected revision records. Adjacent text with different kinds, authors, dates, or move names cannot merge.
  - Whole formulas retain the enclosing revision wrappers; formula-internal revisions remain mixed XML inside `equation`. See [equations](../objects/equation.md).
  - Floating text-box references and their separately emitted stories both retain the enclosing review status.

- **Absence and defaults**
  - No wrappers in final/original.

- **Example**
  - `<w:moveFrom><w:r><w:t>Moved</w:t></w:r></w:moveFrom>` contributes no final text, `Moved` in original, and `<move-from>Moved</move-from>` in semantic review.

- **Limits**
  - Existing current run properties are read. `rPrChange`, `pPrChange`, tracked paragraph-mark deletion, and table/row/cell revisions require separate reconstruction and are not covered by inline visibility.

- **Diagnostics**
  - `REVISION_INSERTION_INCLUDED` and `REVISION_DELETION_SKIPPED` are emitted on encountering the respective wrappers regardless of the selected view; code names do not themselves establish visibility.

### `author`

- **Output**
  - `ins|del|move-from|move-to/@author`.

- **OOXML**
  - Revision `@w:author`

- **IR**
  - `Revision.author: str`

- **Parsing**
  - Copy nonempty value in review mode.

- **Absence and defaults**
  - Omitted.

### `date`

- **Output**
  - `ins|del|move-from|move-to/@date`.

- **OOXML**
  - Revision `@w:date`

- **IR**
  - `Revision.date: str`

- **Parsing**
  - Copy nonempty source string; no timezone conversion.

- **Absence and defaults**
  - Omitted.

### `moveName`

- **Output**
  - `move-from|move-to/@name`, connecting the source/destination when the saved range name exists.
- **OOXML**
  - `w:moveFromRangeStart/@w:name` and `w:moveToRangeStart/@w:name` name the move. Each range ends at its matching `moveFromRangeEnd` or `moveToRangeEnd` with the same `@w:id` as its own start.
- **IR**
  - `Revision.moveName: str`.
- **Parsing**
  - Track active ranges across paragraphs in one story, including body-level range markers and markers in block controls. Capture the active name for the corresponding source/destination wrapper. Text-box stories have separate state; ancillary item boundaries clear range state.
  - Numeric wrapper IDs and source/destination range IDs are not move-pair keys. Do not infer a relationship from matching text or authors. With no saved active name, retain direction without a name attribute.
- **Example**
  - Source and destination in ranges named `move1` produce `<move-from name="move1">text</move-from>` and `<move-to name="move1">text</move-to>` in semantic review.
