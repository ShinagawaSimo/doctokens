# Pagination

[DOCX](../README.md) / Pagination

Page numbers describe stored pagination hints. They are not calculated by laying out fonts, margins, or paper.

## Fields

### `number`

- **Output**
  - DTP isolated `<page=N>`; DTX `<page number="N"/>`.

- **OOXML**
  - `w:lastRenderedPageBreak`, `w:br[@w:type="page"]`, section boundaries.

- **IR**
  - `Block.page: int`

- **Parsing**
  - Start at 1. Flush preceding pending breaks. Add the count of manual-page-break hints to this paragraph start; count leading calculated-break sentinels to find its first content page.

- **Absence and defaults**
  - Empty paragraphs without objects/controls are discarded unless requested; their calculated/manual breaks are discarded. Section breaks on discarded paragraphs still leave a pending page.

- **Notes**
  - Manual breaks currently shift the paragraph as a whole and add a newline; calculated breaks retain an inline boundary.

### `pageBreak`

- **Output**
  - No text; controls a page milestone.

- **OOXML**
  - `w:lastRenderedPageBreak`

- **IR**
  - `Run.pageBreak: bool`

- **Parsing**
  - Split text/object segments and insert `{"text": "", "pageBreak": True}` between them.

- **Absence and defaults**
  - Absent for ordinary runs.

### `pageEnd`

- **Output**
  - Internal selection bound.

- **OOXML**
  - Last calculated break in a block or its nested content.

- **IR**
  - `Block.pageEnd: int`

- **Parsing**
  - Paragraph: `page_start + inline_page_breaks`; table: maximum descendant end page.

- **Absence and defaults**
  - Absent when not needed.

### `pageSegments`

- **Output**
  - Fallback input to page selection.

- **OOXML**
  - Calculated breaks in a paragraph.

- **IR**
  - `ParagraphBlock.pageSegments: list[dict[str, object]]`

- **Parsing**
  - Created when inline breaks exist and `include_runs=False`; each record has `page` and `text`.

- **Absence and defaults**
  - Not constructed when runs are retained.


## Source references

- [RunParser._handle_child](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L107)
- [DocumentBodyParser.parse_paragraph](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/scanner.py#L185)
- [_append_body](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L45)
- [_append_cell_content](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L222)
