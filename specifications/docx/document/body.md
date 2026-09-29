# Document body

[DOCX](../README.md) / Document body

The main part is `word/document.xml`. Body blocks retain XML order, including content-control expansion.

## Fields

### `body`

- **Output**
  - DTX `document/body`; DTP body following its header.

- **OOXML**
  - `w:document/w:body`

- **IR**
  - `ParsedDocument.blocks: list[Block]`

- **Parsing**
  - Dispatch direct `p`, `tbl`, `sdt`, `sectPr`. Do not hoist table descendants. Skip body-level bookmark/proofing/permission markers.

- **Absence and defaults**
  - No rendered blocks: DTX still emits page 1.

- **Diagnostics**
  - `UNSUPPORTED_BODY_CHILD`: other direct body children. Unhandled children inside `sdtContent` are currently skipped without this warning.

### `id`

- **Output**
  - Internal locator; no general DTX block ID.

- **OOXML**
  - Allocation when parsing a paragraph or constructing a table segment.

- **IR**
  - `ParagraphBlock.id`, `HeadingBlock.id`, `TableBlock.id: str`

- **Parsing**
  - `b1`, `b2`, ... from one document allocator. Empty discarded paragraphs can consume IDs; nested blocks also allocate. Table segments have distinct block IDs but share `tableId`.

### `type`

- **Output**
  - `p`, `hN`, or `table` projection.

- **OOXML**
  - `w:p`, resolved style outline, `w:tbl`.

- **IR**
  - `Block.type: Literal["paragraph", "heading", "table"]`

- **Parsing**
  - Determine type during extraction, before rendering.

### `part`

- **Output**
  - Relationship and diagnostic context.

- **OOXML**
  - Owning package part.

- **IR**
  - `Block.part: str`

- **Parsing**
  - Body and nested table blocks use `word/document.xml`.

### `order`

- **Output**
  - Internal source-order counter.

- **OOXML**
  - Traversal of paragraphs and tables.

- **IR**
  - `Block.order: int`

- **Parsing**
  - Increment on paragraph/table entry; nested blocks also increment. Preserve list order rather than sorting by this counter.


## Source references

- [DocumentBodyParser.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/scanner.py#L95)
- [DocumentBodyParser._parse_sdt](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/scanner.py#L163)
- [TableParser._make_block](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/tables.py#L79)
