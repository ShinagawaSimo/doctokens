# Revisions

[DOCX](../README.md) / Revisions

The selected view determines which saved revision text participates in output.

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

- **Diagnostics**
  - Invalid enum: `ValueError`.

### `revision`

- **Output**
  - Semantic `<ins>` or `<del>`.

- **OOXML**
  - `w:ins/w:moveTo/w:del/w:moveFrom`

- **IR**
  - `Run.revision: "inserted" | "deleted"`

- **Parsing**
  - Assign only in review mode. Deletions concatenate descendant `w:delText` into one run; deleted inline formatting/objects are not reconstructed.

- **Absence and defaults**
  - No wrappers in final/original.

- **Diagnostics**
  - `REVISION_INSERTION_INCLUDED` and `REVISION_DELETION_SKIPPED` are emitted on encountering the respective wrappers regardless of the selected view; code names do not themselves establish visibility.

### `author`

- **Output**
  - `ins|del/@author`.

- **OOXML**
  - Revision `@w:author`

- **IR**
  - `Run.revisionAuthor: str`

- **Parsing**
  - Copy nonempty value in review mode.

- **Absence and defaults**
  - Omitted.

### `date`

- **Output**
  - `ins|del/@date`.

- **OOXML**
  - Revision `@w:date`

- **IR**
  - `Run.revisionDate: str`

- **Parsing**
  - Copy nonempty source string; no timezone conversion.

- **Absence and defaults**
  - Omitted.


## Source references

- [InlineParser._append_inserted_runs](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/inline.py#L223)
- [InlineParser._append_deleted_run](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/inline.py#L249)
- [_append_run_text](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L119)
