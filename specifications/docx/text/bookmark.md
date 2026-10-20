# Bookmarks

[DOCX](../README.md) / Bookmarks

Bookmarks provide target names for parsed internal navigation.

## Fields

### `anchor`

- **Output**
  - `p|hN/@anchor` in DTX; no plain mark.

- **OOXML**
  - `w:bookmarkStart/@w:name`

- **IR**
  - `ParagraphBlock.anchors: list[str]`

- **Parsing**
  - Keep nonempty names not starting `_`; deduplicate within block. After parsing, remove names not used by parsed run links. Renderer selects the first retained name used by its anchor scan.

- **Absence and defaults**
  - Unreferenced names are omitted.

- **Notes**
  - Current renderer scans links in top-level text blocks for emitted anchors; bookmarks used only inside table content may not receive a target attribute.
