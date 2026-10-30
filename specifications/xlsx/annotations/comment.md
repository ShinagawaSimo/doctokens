# Cell notes

[XLSX](../README.md) / Cell notes

Legacy comments are represented as cell notes; threaded conversations are independent.

## Processing

Invalid cell ref is skipped. Missing part → COMMENTS_PART_MISSING; invalid XML → COMMENTS_XML_INVALID. Plain appends text/status to ordinary, checkbox and rich-value cells without author/ID metadata. Both XML densities retain known authors, IDs and cell targets.

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
  - Nonnegative int index, default 0; invalid/negative/out-of-range → empty. Omit empty author attributes, rather than selecting another author.

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

### `status`

- **Output**
  - `comment/@status="unknown"`; plain `[comment status=unknown] TEXT`.
- **Parsing**
  - Legacy cell notes do not declare modern review completion. Do not invent
    active/resolved state from their content or from the absence of a flag.
