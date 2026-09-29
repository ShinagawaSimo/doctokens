# Sections

[DOCX](../README.md) / Sections

Section membership follows section boundaries in document order.

## Fields

### `number`

- **Output**
  - `<section number="2">...</section>` in both XML densities; DTP emits `[Section N]` when section grouping is active.

- **OOXML**
  - `w:p/w:pPr/w:sectPr`, direct `w:body/w:sectPr`.

- **IR**
  - `Block.section: int`

- **Parsing**
  - A paragraph sectPr ends its section after that paragraph. The next parsed block advances the section and page. A single default section is removed from top-level blocks. Render sections if any block has section != 1.

- **Absence and defaults**
  - Without a retained section field, use 1.

- **Notes**
  - Current pagination advances at section breaks without distinguishing `continuous`, odd-page, and even-page layout semantics.


## Source references

- [BodySections._begin_section](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/sections.py#L35)
- [DocumentBodyParser.parse_paragraph](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/scanner.py#L185)
- [_append_body](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L45)
