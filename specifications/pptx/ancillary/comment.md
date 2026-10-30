# Comments

[PPTX](../README.md) / Comments

Classic PresentationML and modern PowerPoint comments use their own namespaces,
relationships and author catalogs. Root comments and saved replies are read
separately. All densities retain text and review state. Plain emits
`[comment status=STATUS] TEXT` without IDs or collaboration/target metadata;
both XML densities retain useful identities, ownership and reply relationships.

## Processing

Classic comments use PresentationML/main cmLst/cm/text and the standard
comments/commentAuthors relationships. Modern comments use
`http://schemas.microsoft.com/office/powerpoint/2018/8/main` cmLst/cm/txBody and
replyLst/reply, with `http://schemas.microsoft.com/office/2018/10/relationships/`
comments and authors relationships.

Unsupported namespaces are not accepted by local-name coincidence. Read direct
comment bodies only; replies never become part of the parent's text.

## Fields

### `id`

- **Output**
  - `comment/@id` and per-slide `comment-ref/@id` in both XML densities.
- **IR**
  - `CommentItem.id`.
- **Parsing**
  - Allocate cmt1, cmt2, ... across retained classic/modern parts and replies.
  - An unreadable part retains one navigable placeholder.

### `text`

- **Output**
  - Comment character data; semantic adds supported inline reading marks.
- **OOXML**
  - Classic p:text; modern direct txBody DrawingML paragraphs and runs.
- **IR**
  - `CommentItem.text` and optional `runs`.
- **Parsing**
  - Preserve spaces, empty paragraphs, saved field text, LF and tabs.
  - Modern semantic/session reads retain direct/inherited paragraph run
    emphasis, theme-resolvable colors, hyperlinks and equations. Structural
    projects the same readable content without character emphasis.
  - Missing optional or explicitly empty bodies remain valid empty comments.

### `author`

- **Output**
  - Nonempty `comment/@author` in structural/semantic; omitted from plain.
- **OOXML**
  - authorId resolved through the corresponding family author catalog.
- **Parsing**
  - Keep the display name; omit unresolved/empty authors without inventing one.

### `date`

- **Output**
  - Nonempty `comment/@date` in structural/semantic; omitted from plain.
- **OOXML**
  - Classic dt or modern created.
- **Parsing**
  - Preserve the saved timestamp without conversion.

### `parent`

- **Output**
  - Reply `comment/@parent` in both XML densities.
- **OOXML**
  - Modern root cm/replyLst/reply containment.
- **Parsing**
  - Use the enclosing comment's generated ID. A reply inherits the declared
    slide association and, without its own target, the resolved parent shape.

### `status`

- **Output**
  - `comment/@status="active|resolved|closed|unknown"`; plain uses the same state.
- **OOXML**
  - Modern comment/reply status.
- **IR**
  - `CommentItem.status: AnnotationStatus`.
- **Parsing**
  - Modern missing status uses the format's active default. Preserve resolved
    and closed independently. Invalid values emit COMMENT_STATUS_INVALID and
    remain unknown. Classic comments and unreadable placeholders are unknown.
  - Do not infer completion from the message or the existence of replies.

### `slide`

- **Output**
  - `comment/@slide="slideN"` and references under the associated slide.
- **OOXML**
  - Owning slide relationship or explicit command sldMk/@sldId.
- **Parsing**
  - Resolve through validated slide references. An unresolved locator remains
    unresolved; the existence of only one slide does not assign ownership.

### `shape`

- **Output**
  - `comment/@shape` and `comment-ref/@shape` when exact resolution succeeds.
- **OOXML**
  - The final supported drawing moniker id and/or creationId, matched against
    cNvPr and DrawingML creation identity on the resolved slide.
- **IR**
  - Internal `CommentTarget` retains only identities needed for matching.
- **Parsing**
  - Require all declared components to match one retained shape. Group
    ancestors alone do not identify a child. Template/master targets are not
    matched against ordinary slide shapes by coincident IDs.
  - Retain a shape explicitly targeted by a modern comment before decoration
    filtering, then refer to its final compact shape-id.
  - Do not parse comment x/y positions or infer a nearest shape.
  - Raw anchor/moniker trees, source GUIDs, source namespaces and unconverted
    text/table offsets are not retained as public comment fields. The reader
    does not claim to reconstruct exact character ranges.

### `unparsed`

- **Output**
  - A known unreadable part/body retains unsupported markers in XML and readable
    Unparsed labels in plain, with status unknown.
- **Diagnostics**
  - COMMENTS_PART_MISSING, COMMENTS_XML_INVALID, COMMENTS_ROOT_UNSUPPORTED,
    COMMENT_BODY_CHILD_UNSUPPORTED and COMMENT_ELEMENT_UNSUPPORTED.
- **Parsing**
  - A readable saved fallback represents the content once. Generated labels
    are not searched as source text. Format/author/default fallback alone is
    not an unreadable-element placeholder.
