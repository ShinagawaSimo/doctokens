# Cell notes

[XLSX](../README.md) / Cell notes

Legacy comments are represented as cell notes; threaded conversations are independent.

## Processing

Invalid cell ref is skipped. Missing part → COMMENTS_PART_MISSING; invalid XML → COMMENTS_XML_INVALID. Plain appends comment text to ordinary cell values; checkbox/rich-value early-return paths do not append these comments.

## Fields

### `comment`

- **Output**
  - grid/comments/comment text; cell/comment-ref.

- **OOXML**
  - First comments relationship → s:commentList/s:comment/s:text.

- **IR**
  - `Cell.comment: str`

- **Parsing**
  - Join itertext; missing text → empty. Later notes on same cell overwrite. Full-sheet parsing creates blank cells for valid absent refs; parse windows do not.

### `commentAuthor`

- **Output**
  - comment/@author.

- **OOXML**
  - comment/@authorId → s:authors/s:author list.

- **IR**
  - `Cell.commentAuthor: str`

- **Parsing**
  - int index, default 0; invalid/out-of-range → empty. Negative indices follow Python list indexing when within bounds.

### `id`

- **Output**
  - comment/@id.

- **OOXML**
  - Emitted grid traversal.

- **IR**
  - Derived string.

- **Parsing**
  - comment0, comment1, ... restarted per emitted grid; includes note with empty string.

### `cell`

- **Output**
  - comment/@cell.

- **OOXML**
  - Note cell ref.

- **IR**
  - `Cell.ref`

- **Parsing**
  - Use original/created cell ref. Only emitted rows contribute comments; a shadow cell can contribute a comment record without a cell comment-ref.


## Source references

- [apply_comments](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L147)
- [_apply_legacy_comments](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L179)
- [_comment_records](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L312)
