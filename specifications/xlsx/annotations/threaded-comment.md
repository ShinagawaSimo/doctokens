# Threaded comments

[XLSX](../README.md) / Threaded comments

Modern comments retain their source conversation order within each cell.

## Processing

Read only first threadedComment relationship for the sheet. Missing part → THREADED_COMMENTS_PART_MISSING; invalid XML → THREADED_COMMENTS_XML_INVALID. Invalid ref is skipped; absent target cells follow the same creation rule as legacy notes.

## Fields

### `id`

- **Output**
  - comment/@id; comment-ref/@id.

- **OOXML**
  - threadedComment/@ref and per-cell ordinal.

- **IR**
  - `ThreadedComment.id: str`

- **Parsing**
  - thread-{ref}-{ordinal}, starting1. Source @id maps to this generated ID.

### `text`

- **Output**
  - comment character data.

- **OOXML**
  - Direct local-name text child.

- **IR**
  - `str`

- **Parsing**
  - Join itertext; missing → empty.

### `author`

- **Output**
  - comment/@author.

- **OOXML**
  - @personId → xl/persons/person.xml person/@id,@displayName.

- **IR**
  - `str`

- **Parsing**
  - Retain nonempty resolved display name. Missing people catalog → no author. Invalid people XML → COMMENT_PEOPLE_XML_INVALID.

### `date`

- **Output**
  - comment/@date.

- **OOXML**
  - threadedComment/@dT.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty string.

### `parentId`

- **Output**
  - comment/@parent.

- **OOXML**
  - threadedComment/@parentId.

- **IR**
  - `str`

- **Parsing**
  - Validate source-ID links, then map to generated IDs. Dangling/self/cyclic links are excluded by valid_parent_links without a parser warning.

### `resolved`

- **Output**
  - comment/@resolved=true.

- **OOXML**
  - threadedComment/@done.

- **IR**
  - `bool`

- **Parsing**
  - Present lower-case value outside 0/false/off/none → true; store true only.

### `mentions`

- **Output**
  - Internal mention ranges.

- **OOXML**
  - Descendant mention.

- **IR**
  - `list[AnnotationMention]`

- **Parsing**
  - Retain recognized people; see [mentions](mention.md). No DTX mention elements.


## Source references

- [_apply_threaded_comments](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/comments.py#L118)
- [valid_parent_links](../../../packages/ooxml_llm_core/src/ooxml_llm_core/annotations.py#L34)
