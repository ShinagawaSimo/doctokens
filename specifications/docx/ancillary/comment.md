# Comments

[DOCX](../README.md) / Comments

Saved ancillary content is parsed independently of body layout.

## Processing

XML read failure: `ANCILLARY_XML_PARSE_FAILED`; omit the failed part. DTX includes retained comments in both XML densities. Plain appends referenced comments, then unreferenced comments, under `[Comments]` as `[cmt<ID>: text]`.

## Fields

### `id`

- **Output**
  - `supplemental/comments/comment/@id`.

- **OOXML**
  - `word/comments.xml/w:comments/w:comment`; `@w:id`

- **IR**
  -  `AncillaryItem.id: str | None`

- **Parsing**
  - Copy nonempty source id; skip missing IDs.

### `locator`

- **Output**
  - `comment/@locator`.

- **OOXML**
  - Derived from group and ID.

- **IR**
  - `AncillaryItem.loc: str`

- **Parsing**
  - `"comments." + id`.

### `text`

- **Output**
  - DTX `comment` character data and inline elements.

- **OOXML**
  - `word/comments.xml/w:comments/w:comment`

- **IR**
  - `AncillaryItem.text: str`

- **Parsing**
  - Join retained paragraph content with LF. Flatten table cells with ` | ` and rows with LF. Skip whitespace-only content without objects.

### `runs`

- **Output**
  - DTX inline semantics; DTP readable content.

- **OOXML**
  - `word/comments.xml/w:comments/w:comment` child p/tbl/sdt/sdtContent/smartTag.

- **IR**
  - `AncillaryItem.runs: list[Run]`

- **Parsing**
  - Use the inline parser; insert separator runs between retained containers. Retain controls around their runs; tables have no table IR here.

### `rawHints`

- **Output**
  - Internal diagnostic detail.

- **OOXML**
  - `word/comments.xml/w:comments/w:comment`

- **IR**
  - `AncillaryItem.rawHints: list[RawHint]`

- **Parsing**
  - Keep only if RAW_HINTS, include_raw_hints, and nonempty.

### `author`

- **Output**
  - `comment/@author`.

- **OOXML**
  - `w:comment/@w:author`

- **IR**
  - `AncillaryItem.author: str`

- **Parsing**
  - Copy nonempty string.

### `date`

- **Output**
  - `comment/@date`.

- **OOXML**
  - `w:comment/@w:date`

- **IR**
  - `AncillaryItem.date: str`

- **Parsing**
  - Copy nonempty string without conversion.

### `anchor`

- **Output**
  - `comment/@anchor`.

- **OOXML**
  - Body comment-range/reference association.

- **IR**
  - `AncillaryItem.anchor: str`

- **Parsing**
  - Use the body parser comment-anchor lookup if present.

### `parent`

- **Output**
  - `comment/@parent`.

- **OOXML**
  - `word/commentsExtended.xml/*/commentEx/@paraIdParent` (local names).

- **IR**
  - `AncillaryItem.parentId: str`

- **Parsing**
  - Map the last paragraph paraId of each retained comment to its comment ID. Resolve parent through this map.

- **Absence and defaults**
  - Absent for roots.

- **Diagnostics**
  - Unresolved parent: `COMMENT_PARENT_UNRESOLVED`, locator `word/commentsExtended.xml:<comment-id>`.

### `resolved`

- **Output**
  - `comment/@resolved="true"`.

- **OOXML**
  - `commentEx/@done`

- **IR**
  - `AncillaryItem.resolved: bool`

- **Parsing**
  - Store true when Word bool helper accepts done; false is not stored. Thread metadata requires COMMENT_THREADING.


## Source references

- [AncillaryParser._parse_comments](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L120)
- [AncillaryParser._container_content](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L247)
- [_append_supplemental](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L272)
