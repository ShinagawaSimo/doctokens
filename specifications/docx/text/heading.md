# Headings

[DOCX](../README.md) / Headings

Heading identity comes from a referenced style outline level.

## Processing

Identity, text, runs, paragraph properties, controls, and page fields have the same rules as [paragraphs](paragraph.md) and [body blocks](../document/body.md). In table cells the current DTX renderer uses `p` even when the nested IR block is a heading.

## Fields

### `level`

- **Output**
  - DTX `h{level}`; plain text without Markdown heading syntax.

- **OOXML**
  - `w:style/w:pPr/w:outlineLvl/@w:val` reached through paragraph style.

- **IR**
  - `HeadingBlock.level: int`

- **Parsing**
  - Resolve explicit outline < 9 as `outline_level + 1`; otherwise follow `basedOn`. No font-size/name/weight inference.

- **Absence and defaults**
  - Missing style or unresolved chain: ordinary paragraph.

- **Diagnostics**
  - `MISSING_STYLES`, `INVALID_OUTLINE_LEVEL`, `STYLE_INHERITANCE_CYCLE` according to style parsing.

- **Notes**
  - The serializer emits `h1` through `h9` for resolved levels 1 through 9.

### `headingSource`

- **Output**
  - Internal classification evidence.

- **OOXML**
  - Style outline resolution.

- **IR**
  - `Literal["style"]`

- **Parsing**
  - Assigned when the paragraph becomes a heading.


## Source references

- [StyleMap._resolve_heading_level](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/styles.py#L90)
- [_append_block](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L65)
- [_append_cell_content](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L222)
