# Speaker notes

[PPTX](../README.md) / Speaker notes

Notes are attached to their source slide.

## Fields

### `text`

- **Output**
  - `speaker-notes` text; plain `[Notes: text]`.

- **OOXML**
  - First notesSlide relationship; notes p:cSld/p:spTree/p:sp/p:txBody.

- **IR**
  - `SlideBlock.notes: str | None`

- **Parsing**
  - Skip placeholders sldNum/dt/hdr/ftr/slideImage; extract other direct sp text; join nonempty shapes with two LF.

- **Absence and defaults**
  - None when no content.

- **Diagnostics**
  - NOTES_PART_MISSING, NOTES_XML_INVALID or NOTES_MISSING_SPTREE retain
    `[Unparsed speaker notes]` for a present notes relationship that cannot
    be read. No notes relationship remains ordinary absence.
  - An unreadable selected shape alternative in the note tree retains its
    unreadable-shape marker; readable alternatives and property containers
    do not create an extra marker. Notes remain a flattened text projection
    in both XML densities, including these markers.

### `notesSearch`

- **Output**
  - Internal source lines used by text search.
- **OOXML**
  - The same retained note shapes and paragraphs.
- **IR**
  - `SlideBlock.notesSearch: list[str]`.
- **Parsing**
  - Preserve the note text's existing line boundaries, including separation
    between shapes. Replace generated inline unreadable-content markers by
    a boundary; do not search the generated label or join text across a gap.
    An unreadable whole part contributes no searchable source text.
