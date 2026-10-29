# Revisions

[DOCX](../README.md) / Revisions

The selected view determines saved content, paragraph boundaries, table structure, and supported historical reading properties. It does not repaginate Word content or reconstruct editable typography/geometry.

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
  - The same view selects inserted/deleted rows and cells before computing table coordinates or merge state. Final omits deleted structure; original omits inserted structure; review retains both and emits semantic structural review marks.

- **Diagnostics**
  - Invalid enum: `ValueError`.

### `revisions`

- **Output**
  - Semantic `<ins>`, `<del>`, `<move-from>`, or `<move-to>`, wrapping both text and objects. Nested revisions nest in source order, outermost first.
  - Plain/structural retain the selected text and objects without review wrappers.

- **OOXML**
  - `w:ins/w:moveTo/w:del/w:moveFrom`

- **IR**
  - `Run.revisions`, `TableRow.revisions`, and `TableCell.revisions`: `list[Revision]`, populated only for review.
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
  - Reconstruct the saved properties supported by the reading model. Ignored fonts, exact dimensions, and other editable-layout fields remain outside the public reading projection. Saved page hints remain saved hints in all revision views.

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

### `paragraphMark`

- **Output**
  - Semantic review appends `<paragraph-break revision="inserted|deleted|moved-from|moved-to" author="..." date="..."/>` to the affected paragraph. Ancillary flattened runs can carry the same mark.
- **OOXML**
  - Tracked insertion/deletion/move on `w:pPr/w:rPr`.
- **IR**
  - Optional `TextBlock.paragraphMark` / `Run.paragraphMark: Revision`.
- **Parsing**
  - When the selected view removes a paragraph mark, accumulate adjacent paragraphs into one logical paragraph, without inventing a space. Use the surviving last paragraph's selected properties and perform numbering once for the group. Preserve runs, controls, bookmarks, and inline page milestones from every contributing paragraph.
  - Final joins at deleted/move-source marks; original joins at inserted/move-destination marks. Review keeps boundaries and records the mark's saved revision identity. Groups do not cross table/cell/story boundaries.
- **Example**
  - `First` followed by a deleted paragraph mark and `Second` yields `FirstSecond` in final, two paragraphs in original, and two review paragraphs with a deleted paragraph-break marker.

### `propertyChanges`

- **Output**
  - Semantic `<format-change scope="run|paragraph|table|row|row-table|cell|numbering" before="..." after="..." author="..." date="...">content</format-change>` for a changed supported property set. Lower densities omit review metadata.
- **OOXML**
  - `rPrChange`, `pPrChange`, `tblPrChange`, `trPrChange`, `tcPrChange`, `tblPrExChange`, `tblGridChange`, cellMerge, and numPr/numberingChange.
- **IR**
  - `ReviewMarkup.propertyChanges: list[PropertyChange]`; each record stores scope, before/after descriptions, and saved author/date.
- **Parsing**
  - Original selects the nested saved previous property set, including an explicitly empty set. Final/review select current properties. The selected set participates in the normal defaults/style/direct-format cascade.
  - Run before/after descriptions use effective visible reading formats. Structural descriptions include the supported style, alignment, outline, numbering, borders, cell fill, grid positions/spans, region settings, and merge relationships. Descriptions sort `key=value` pairs and use `normal` for an empty set. Geometry-only changes do not add review markup.
  - Table grid history affects logical column count. Tracked cell merge selects vMergeOrig for original and vMerge for final/review, describing cont/rest as continue/restart.
  - Saved numberingChange definitions restore the original label format. Review formats the established counter with previous and current definitions, annotating the marker without advancing counters twice. It does not infer a previous counter value that was not saved.
  - With no saved previous property set, retain the available current set; do not infer an absent historical value.
- **Example**
  - Saved current bold with an empty previous rPr yields plain `Old` in original, `<b>Old</b>` in final, and `<format-change after="bold=true" before="normal" scope="run"><b>Old</b></format-change>` in semantic review.
