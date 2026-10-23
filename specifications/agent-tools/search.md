# Text location

[Agent tools](README.md) / Text location

`find_document_text` accepts DOCX, PPTX, and XLSX paths or pinned document IDs.
It uses [literal matching and excerpts](../common/text-search.md), with no density
argument and no requirement to inspect first.

## Fields

### `parts`

- **Output**
  - One text part per matched paragraph/cell: `selection` is the locator,
    `media_type="text/plain"`, and the body is the excerpt. Empty searches return
    an empty list. MCP emits each excerpt once as native text, referenced through
    `content_index`; direct calls use `text`.
- **Processing**
  - Use the standard first-content budget and `read_result` for an incomplete
    excerpt. A root `next_offset` continues matching units, while a part's
    `result_id`/`next_offset` continues that part's characters. Large JSON metadata
    uses the usual explicit application/json fragment transport.

### `selection`

- **Output**
  - DOCX: `source`, `block_id`, `page_start` and an optional `page_end` for a
    paragraph spanning saved-page hints; tables add `table_id`, one-based `row`
    and `column`; textboxes can add `textbox_id` and an ancillary `story_source`.
    Ancillary content uses `item_id`
    and a paragraph ordinal, with an anchor page/block when known. A page is not
    fabricated for an unanchored story.
  - PPTX: `slide_start`, `source`, and shape/paragraph or table-cell coordinates.
    Table rows/columns and paragraph ordinals are one-based. Notes/comments carry
    their source and a comment item ID when applicable.
  - XLSX: exact `sheet` and `range_spec` identifying one saved cell.
- **Processing**
  - Pass the returned page/slide fields to the corresponding reader; for a
    single-page/slide follow-up set its end equal to its start. XLSX sheet and
    range_spec can be used directly. Other locator fields identify the object
    within that selected content, not extra reader arguments.

### `include_headers_footers`

- **Default**
  - `false`; only valid for DOCX when enabled.
- **Processing**
  - Default DOCX scope includes body paragraphs, table cells, textboxes,
    footnotes, endnotes, and comments. Headers/footers are opt-in and searched
    once by source, not repeated per saved page. DOCX ancillary content retains
    paragraph and cell boundaries for search. PPTX includes body, table and
    textbox text, notes and comments; saved flattened notes/comments use retained
    line units. Separate paragraphs/cells are never concatenated for matching.

### `sheets`

- **Default**
  - `null`; XLSX searches all sheets.
- **Processing**
  - XLSX-only exact names. An empty list searches no sheets; unknown names are
    rejected. Before a full session exists, explicit sheets use a structural
    parse restricted to those sheets, without opening a full workbook session.
    Other searches use the pinned format session. Parsing is not promised to
    stop at the first returned hit.
  - This entry searches displayed cell text. Formula, comment, hyperlink and
    defined-name searches keep the existing `find_xlsx_cells` contract.

### `next_offset`

- **Output**
  - Matching-unit continuation, or `null` when complete. No redundant total or
    has-more field is emitted.
