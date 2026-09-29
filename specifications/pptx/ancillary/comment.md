# Comments

[PPTX](../README.md) / Comments

Comments are emitted after slides, with per-slide references where resolution succeeds.

## Processing

Only the comments relationship URI handled by CommentsParser participates. Missing part → COMMENTS_PART_MISSING; invalid XML → COMMENTS_XML_INVALID. PresentationML classic root reports LEGACY_COMMENTS_PARSED. Comment content is not filtered by empty text.

## Fields

### `id`

- **Output**
  - comment/@id; comment-ref/@id.

- **OOXML**
  - cm traversal through comments relationships.

- **IR**
  - `CommentItem.id: str`

- **Parsing**
  - cmt1,cmt2,...; map source idx or id for parent resolution.

### `text`

- **Output**
  - Comment character data.

- **OOXML**
  - Classic PresentationML `p:cm/p:text`; modern comment's direct `text` child with descendant `t` text nodes.

- **IR**
  - `str`

- **Parsing**
  - For classic `p:cm`, concatenate text content of its direct `p:text` child, preserving XML-decoded leading/trailing whitespace and line breaks. For modern comments, concatenate descendant `t` nodes inside the direct `text` child in document order.
  - A missing body child and an empty body child both serialize as empty comment character data. Neither removes the comment or its slide association. Character data is XML-escaped during serialization.

### `author`

- **Output**
  - comment/@author.

- **OOXML**
  - cm/@authorId → cmAuthor/@id, @name.

- **IR**
  - `str`

- **Parsing**
  - Default empty string. Missing/malformed author part is skipped silently.

### `date`

- **Output**
  - comment/@date.

- **OOXML**
  - cm/@dt.

- **IR**
  - `str`

- **Parsing**
  - Copy nonempty value.

### `parentId`

- **Output**
  - Fallback comment/@parent.

- **OOXML**
  - cm/@parentId.

- **IR**
  - `str`

- **Parsing**
  - Retain raw ID; attempt same-part idx/id map. Unresolved → COMMENT_PARENT_UNRESOLVED.

### `parentCommentId`

- **Output**
  - Preferred comment/@parent.

- **OOXML**
  - Resolved raw parent ID.

- **IR**
  - `str`

- **Parsing**
  - Generated cmtN parent ID.

### `slideId`

- **Output**
  - comment/@slide.

- **OOXML**
  - cm/@slideId, fallback @slide, fallback relationship source slide part.

- **IR**
  - `str`

- **Parsing**
  - Map through validated slide locators; attached comment is rewritten to slideN. A lone slide can receive otherwise unresolved comments.

### `shapeId`

- **Output**
  - comment/@shape and comment-ref/@shape.

- **OOXML**
  - Comment position and positioned shapes.

- **IR**
  - `str`

- **Parsing**
  - Choose nearest shape center by Manhattan distance only if geometry fields exist. Default public plans omit those fields, so ordinary comments have no inferred shape.

### `x`

- **Output**
  - Internal horizontal position.

- **OOXML**
  - First pos/@x.

- **IR**
  - `int`

- **Parsing**
  - Parse integer; missing/malformed omitted.

### `y`

- **Output**
  - Internal vertical position.

- **OOXML**
  - First pos/@y.

- **IR**
  - `int`

- **Parsing**
  - Parse integer; missing/malformed omitted. If either absolute coordinate exceeds1000 and slide size exists, normalize both to per-mille for attachment.


## Source references

- [CommentsParser.parse](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/ancillary/parts.py#L96)
- [_CommentAttachmentPlan](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L40)
- [PptxParser._attach_comments](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L190)
- [_append_comments](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L207)
