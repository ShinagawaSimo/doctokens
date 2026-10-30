# Comments

[DOCX](../README.md) / Comments

All densities retain comment text and its saved review status. Plain emits
`[comment status=STATUS] TEXT` in source comment order, without IDs, authors,
dates, targets or parent metadata. Both XML densities retain IDs, known authors,
dates, explicit reply parents and positional `comment-ref` relationships.
Semantic additionally retains supported inline reading semantics.

## Fields

### `id`

- **Output**
  - `supplemental/comments/comment/@id` and positional `comment-ref/@id`.
- **OOXML**
  - `word/comments.xml/w:comments/w:comment/@w:id` and body references.
- **IR**
  - `AncillaryItem.id`.
- **Parsing**
  - Preserve a nonempty source ID; skip comments with no required ID.
  - Keep an explicitly empty comment, including a parent with nonempty replies.
  - Plain does not emit IDs or unresolved ID markers.

### `text`

- **Output**
  - Comment character data with supported inline elements in XML.
  - Plain text after the status marker.
- **OOXML**
  - Comment p/tbl/sdt/sdtContent/smartTag contents.
- **IR**
  - `AncillaryItem.text` and `runs`.
- **Parsing**
  - Join retained paragraph content with LF and flattened table cells with
    ` | `. Use the ordinary saved-content and revision-view readers.
  - Semantic retains supported emphasis, links, controls, equations and review
    marks. Structural retains content and ordinary references without emphasis.
  - Generated unreadable-object labels do not become searchable source text.

### `status`

- **Output**
  - `comment/@status="active|resolved|closed|unknown"` in both XML densities;
    plain always identifies the same state.
- **OOXML**
  - A matching `word/commentsExtended.xml` commentEx record and its done value.
- **IR**
  - `AncillaryItem.status: AnnotationStatus`.
- **Parsing**
  - Read thread/status metadata at every body-reading density and in sessions.
  - A readable matching commentEx defaults done to false: active. Recognized
    1/true/on means resolved; 0/false/off means active, case-insensitively.
  - Missing/unreadable thread metadata or an invalid done value leaves unknown.
    Invalid values emit COMMENT_STATUS_INVALID.
  - Word's supported completion metadata does not produce closed; the shared
    vocabulary preserves that distinct state when another format saves it.
  - Do not infer status from comment wording or from a reply's presence.

### `author`

- **Output**
  - Nonempty `comment/@author` in structural and semantic; omitted from plain.
- **OOXML**
  - Comment `@w:author`.
- **Parsing**
  - Preserve the saved human-readable value; omit an absent/empty value.

### `date`

- **Output**
  - Nonempty `comment/@date` in structural and semantic; omitted from plain.
- **OOXML**
  - Comment `@w:date`.
- **Parsing**
  - Preserve the saved timestamp without timezone conversion or reconstruction.

### `parent`

- **Output**
  - Reply `comment/@parent` referring to a retained comment ID.
- **OOXML**
  - commentEx `@paraIdParent` matched to the parent's last paragraph paraId.
- **IR**
  - `AncillaryItem.parentId`.
- **Parsing**
  - Keep only known, non-self, acyclic links. Unresolved parents emit
    COMMENT_PARENT_UNRESOLVED; invalid self/cyclic links emit COMMENT_PARENT_INVALID.
  - Parent means a conversation reply, not the location the comment discusses.

### `target`

- **Output**
  - The position of `comment-ref` in retained body/table/text-box content
    identifies the supported target context.
- **IR**
  - Internal `AncillaryItem.targetBlock` supports selecting relevant comments.
- **Parsing**
  - Do not emit an internal block number as comment/@anchor: that number is
    not a public body target. Do not repeat the derived comments.ID locator.
  - Page windows retain referenced/associated comments and their explicit
    connected thread context, without importing unrelated comments.
  - References identify reading context, not a reconstructed exact character range.

## Limits

Ancillary XML failures remain diagnostics under the existing ancillary reader.
Unsupported or missing source content is not silently declared empty or active.
No raw paragraph IDs, programmatic locations, source paths or decoder
provenance are added to the routine comment projection.
