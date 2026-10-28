# Bookmarks

[DOCX](../README.md) / Bookmarks

Bookmarks provide target names for parsed internal navigation.

## Fields

### `anchor`

- **Output**
  - `p|hN/@anchor` in DTX; additional referenced names on the same block use empty child `<anchor name="..."/>` elements. No plain mark.

- **OOXML**
  - `w:bookmarkStart/@w:name`

- **IR**
  - `ParagraphBlock.anchors: list[str]`

- **Parsing**
  - Collect nonempty names, including Word-generated `_Ref...` and `_Toc...`; deduplicate within a block.
  - After all parsed stories are assembled, retain only names referenced by links with an anchor and no external href. Scan body, tables, nested tables, text boxes, and parsed supplemental runs. A remote document fragment does not retain an unrelated local bookmark.
  - Emit the first retained name as the block attribute and remaining names as alias elements. Table-cell paragraphs and text-box paragraphs use the same target rules.
  - On a paragraph split across saved page hints, emit its block-level targets only on its first visible fragment. A selected page retains its targets even if the referring link is on another page; it does not import content from that page.

- **Absence and defaults**
  - Unreferenced names are omitted.

- **Notes**
  - Example: `REF _Ref123` renders `<a anchor="_Ref123">saved result</a>` and a retained target `<p anchor="_Ref123">target text</p>`.
  - Names locate retained reading blocks, not exact character-range endpoints. Ordinary empty-paragraph filtering, revision selection, page selection, and table-summary limits still determine which source content is emitted. Bookmarks in flattened ancillary paragraphs are not collected as independent targets.
