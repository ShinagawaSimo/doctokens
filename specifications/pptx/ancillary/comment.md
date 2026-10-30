# Comments

[PPTX](../README.md) / Comments

Comments follow slides in both XML densities. Plain appends a Comments section.
Per-slide references identify comments whose saved ownership can be resolved.

## Processing

The [comment parser](../../../packages/doctokens_powerpoint/src/doctokens_powerpoint/pptx/parsing/modules/ancillary/comments.py)
supports two distinct package structures:

- Classic PresentationML:
  - Namespace: `http://schemas.openxmlformats.org/presentationml/2006/main`.
  - Comments relationship:
    `http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments`.
  - Authors relationship: the same base URI plus `commentAuthors`.
  - Read direct p:cmLst/p:cm and p:cmAuthorLst/p:cmAuthor.
- Modern PowerPoint:
  - Namespace: `http://schemas.microsoft.com/office/powerpoint/2018/8/main`
    (p188 below; the actual source prefix is arbitrary).
  - Comments relationship:
    `http://schemas.microsoft.com/office/2018/10/relationships/comments`.
  - Authors relationship: the same base URI plus `authors`.
  - Read direct p188:cmLst/p188:cm and p188:authorLst/p188:author.
  - Read direct replyLst/reply under each comment, in saved order, after its parent.

Classic author IDs and modern author IDs belong to separate maps. Unsupported
root namespaces are not accepted by local-name coincidence. The
[Open XML SDK comment schema](https://github.com/dotnet/Open-XML-SDK/blob/main/data/schemas/schemas_microsoft_com_office_powerpoint_2018_8_main.json)
defines the modern source structure.

## Fields

### `id`

- **Output**
  - comment/@id and comment-ref/@id.
- **IR**
  - `CommentItem.id: str`.
- **Parsing**
  - Allocate cmt1, cmt2, ... across classic parts, modern parts and replies.
    A reply's generated parent ID points to the enclosing root comment.
    A placeholder for an unreadable comments part also receives one navigation ID.

### `text`

- **Output**
  - Comment character data; plain uses `[cmtN: text]`.
- **OOXML**
  - Classic p:cm/p:text; modern p188:cm/p188:txBody and reply/p188:txBody.
- **IR**
  - `CommentItem.text: str`; optional runs for equations/unreadable regions.
- **Parsing**
  - Classic text preserves all character data in the direct p:text child.
  - Modern text reads direct DrawingML paragraphs, saved a:r/a:t and a:fld/a:t,
    soft breaks and tabs. Separate paragraphs with LF, preserving empty
    paragraphs, leading/trailing spaces and XML-decoded characters.
  - Read only the current comment's direct body. Reply bodies never become
    part of the parent's text. Formatting properties do not enter the text.
    Native equations use the existing inline equation reader.
  - A missing optional txBody or an explicitly empty body is empty content,
    not a decoding failure. Empty comments retain identity and ownership.

### `author`

- **Output**
  - comment/@author.
- **OOXML**
  - Classic cm/@authorId to cmAuthor/@id and @name.
  - Modern cm or reply/@authorId to author/@id and @name.
- **IR**
  - `CommentItem.author: str`.
- **Parsing**
  - Resolve through the corresponding format-family author map.
    Missing/unreadable authors leave an empty author; readable comment text
    remains available without an unreadable-element placeholder.

### `date`

- **Output**
  - comment/@date.
- **OOXML**
  - Classic cm/@dt; modern cm or reply/@created.
- **IR**
  - `CommentItem.date: str`.
- **Parsing**
  - Copy a nonempty saved timestamp; do not infer missing dates.

### `parentCommentId`

- **Output**
  - Reply comment/@parent.
- **OOXML**
  - Modern root cm/replyLst/reply containment.
- **IR**
  - `CommentItem.parentCommentId: str`.
- **Parsing**
  - Use the enclosing root comment's generated ID. Replies inherit its slide
    association and resolved shape association. The source anchor is emitted
    once on the parent, without repeating it on each reply.

### `status`

- **Output**
  - comment/@status for resolved or closed; omit active.
- **OOXML**
  - Modern cm or reply/@status.
- **IR**
  - `CommentItem.status: str`.
- **Parsing**
  - Retain active, resolved or closed; missing status uses active.
    Invalid values emit COMMENT_STATUS_INVALID and do not hide the comment.
    No state is guessed from task progress or the text of a reply.

### `slideId`

- **Output**
  - comment/@slide; comment-ref inside the associated slide.
- **OOXML**
  - Owning slide relationship; modern source pc:sldMk/@sldId when saved.
- **IR**
  - `CommentItem.slideId: str`.
- **Parsing**
  - Resolve source slide IDs/parts against the validated presentation slide
    list and rewrite to slideN. Explicit modern moniker slide IDs take priority.
    Modern comments without a valid slide locator are not assigned to the
    only available slide by inference. Existing classic lone-slide attachment
    remains separate. Window reads include comments of the selected slides.

### `anchors`

- **Output**
  - Parent comment/anchor with @kind; nested moniker elements retain their
    source local kind, attributes and hierarchy.
  - Example:
    `<anchor kind="deMkLst"><moniker kind="sldMkLst"><moniker kind="sldMk" sldId="256"/></moniker><moniker id="2" kind="spMk"/></anchor>`.
- **OOXML**
  - `pc = http://schemas.microsoft.com/office/powerpoint/2013/main/command`:
    sldMkLst, sldLayoutMkLst, sldMasterMkLst.
  - `oac = http://schemas.microsoft.com/office/drawing/2013/main/command`:
    deMkLst, txBodyMkLst, txMkLst, tcMkLst, trMkLst, gridColMkLst.
  - p188:unknownAnchor.
- **IR**
  - `CommentItem.anchors: list[CommentAnchor]`.
- **Parsing**
  - Preserve each direct supported anchor tree, including shape/group
    monikers, text ranges and table indices. Source IDs are not rewritten.
    A saved unknownAnchor stays explicit. A source range is not interpreted as
    a guessed visible-text offset.
  - Raw source anchors remain available even when their target is absent,
    points to a template/group or cannot resolve to a retained shape.

### `shapeId`

- **Output**
  - comment/@shape and comment-ref/@shape when exact resolution succeeds.
- **OOXML**
  - Final oac shape/picture/connector/graphic-frame moniker @id and/or @creationId.
  - Source shape cNvPr/@id and DrawingML 2014 creationId/@id.
- **IR**
  - `CommentItem.shapeId: str`; source identities on ShapeBlock.
- **Parsing**
  - Require all saved identity components to agree with exactly one shape on
    the resolved slide. Ancestor group IDs do not identify a child by
    themselves. Retain an otherwise decorative shape when an exact modern
    comment targets it, then resolve its final compact shape-id.
  - Modern positions never replace source anchors with a nearest-shape guess.
    Classic position-based inference remains available only when internal
    geometry fields exist; default public plans do not populate them.

### `x` and `y`

- **Output**
  - Internal saved position only.
- **OOXML**
  - Direct classic p:pos or modern p188:pos/@x, @y.
- **IR**
  - Optional integer fields on CommentItem.
- **Parsing**
  - Parse valid integers; invalid values emit COMMENT_POSITION_INVALID.
    Modern positions are not used for shape attachment.

### `unparsed`

- **Output**
  - An unreadable part produces a navigable comment containing
    `<unsupported type="comments"/>`; plain uses `[Unparsed comments]`.
  - Unsupported content inside a readable body retains an inline unsupported
    marker at that location while preserving surrounding text.
- **Diagnostics**
  - COMMENTS_PART_MISSING, COMMENTS_XML_INVALID, COMMENTS_ROOT_UNSUPPORTED,
    COMMENT_BODY_CHILD_UNSUPPORTED; classic parts also report
    LEGACY_COMMENTS_PARSED for their missing modern thread metadata.
- **Parsing**
  - A known comments relationship whose part cannot be read establishes the
    existence of comment content, without establishing its count or text.
    Emit one part placeholder rather than silently losing that relationship.
    Generated placeholder text is not searchable source text.
    Unknown elements in comment/reply lists emit COMMENT_ELEMENT_UNSUPPORTED
    with a placeholder; extension-list metadata does not create one.
