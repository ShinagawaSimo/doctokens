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
  - NOTES_PART_MISSING or NOTES_XML_INVALID → None.


## Source references

- [NotesParser.notes_for](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/ancillary/parts.py#L34)
