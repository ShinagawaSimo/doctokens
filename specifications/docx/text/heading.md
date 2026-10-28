# Headings

[DOCX](../README.md) / Headings

Heading identity comes from an explicit paragraph outline level or its referenced style.

## Processing

Identity, text, runs, paragraph properties, controls, and page fields have the same rules as [paragraphs](paragraph.md) and [body blocks](../document/body.md). In table cells the current DTX renderer uses `p` even when the nested IR block is a heading.

## Fields

### `level`

- **Output**
  - DTX `h{level}`; plain text without Markdown heading syntax.

- **OOXML**
  - `w:p/w:pPr/w:outlineLvl/@w:val`, then `w:style/w:pPr/w:outlineLvl/@w:val` reached through paragraph style.

- **IR**
  - `HeadingBlock.level: int`

- **Parsing**
  - A valid direct paragraph value takes precedence: 0..8 yields `outline_level + 1`; 9 explicitly produces an ordinary paragraph.
  - When the direct value is absent or invalid, resolve the style's first explicit outline through `basedOn`. Style value 9 stops inheritance and produces an ordinary paragraph.
  - No font-size/name/weight inference. A direct outline works without styles.xml.

- **Absence and defaults**
  - Missing style or unresolved chain: ordinary paragraph.

- **Diagnostics**
  - An outline element with missing, nonnumeric, or out-of-range value reports `INVALID_OUTLINE_LEVEL` at its owning part/block and falls back to the next applicable source. A missing element does not warn.
  - `MISSING_STYLES`, `STYLE_INHERITANCE_CYCLE` according to style parsing.

- **Notes**
  - The serializer emits `h1` through `h9` for resolved levels 1 through 9.
  - Example: direct outline 0 produces `<h1>Title</h1>`; direct 9 on a heading style produces `<p>Title</p>`.

### `headingSource`

- **Output**
  - Internal classification evidence.

- **OOXML**
  - Paragraph or style outline resolution.

- **IR**
  - `Literal["paragraph", "style"]`

- **Parsing**
  - Assigned when the paragraph becomes a heading; `paragraph` identifies a valid direct value. No provenance attribute is added to DTX.
