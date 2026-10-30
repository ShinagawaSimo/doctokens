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
  - A paragraph sectPr ends its section after that paragraph. The next parsed
    block advances section membership, including a boundary on a discarded
    empty paragraph. A single default section is omitted from top-level blocks.
    Render sections if any block has section != 1.
  - w:type in a section's ending sectPr describes how that same section begins
    relative to its predecessor (ISO/IEC 29500-1 §17.6.22). It does not describe
    the next section. After collecting all selected section properties,
    including the final body sectPr, remove the provisional synthetic page
    increment for each section explicitly beginning continuous.
  - Apply the correction to retained body/nested story page/pageEnd and virtual
    page segments. Saved inline page breaks remain independent milestones.

- **Absence and defaults**
  - Without a retained section field, use 1.

- **Notes**
  - Explicit continuous sections add no page by themselves. The existing
    next-page approximation remains for other section starts; odd/even/column
    placement is not recomputed from fonts, geometry or current rendering.
