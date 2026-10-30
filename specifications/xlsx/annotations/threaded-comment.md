# Threaded comments

[XLSX](../README.md) / Threaded comments

Modern conversations retain source order within their cell. All densities keep
text and review status. Plain appends `[comment status=STATUS] TEXT` without
authors, dates, IDs, parents or target attributes. Structural/semantic retain
those useful fields; semantic additionally identifies explicitly mentioned people.

## Processing

Read the first supported threadedComment relationship for each sheet. Missing
parts emit THREADED_COMMENTS_PART_MISSING; invalid XML emits
THREADED_COMMENTS_XML_INVALID. Skip invalid cell references. Full-sheet reads
can create an annotated empty cell; selected parse windows only annotate
selected existing cells. Checkbox and rich-value cells retain their comments.

## Fields

### `id`

- **Output**
  - `comment/@id` and `comment-ref/@id` in both XML densities.
- **OOXML**
  - Source ref and per-cell ordinal; raw source IDs are temporary link keys.
- **IR**
  - `ThreadedAnnotation.id`.
- **Parsing**
  - Use thread-{ref}-{ordinal}, starting at 1, within the owning sheet.

### `text`

- **Output**
  - Comment character data; plain text follows the status marker.
- **OOXML**
  - Direct text child.
- **Parsing**
  - Join saved character data; missing text is empty content.

### `author`

- **Output**
  - Nonempty `comment/@author` in structural/semantic.
- **OOXML**
  - personId resolved through xl/persons/person.xml.
- **Parsing**
  - Keep the human-readable display name; omit an unresolved name.
  - Invalid people XML emits COMMENT_PEOPLE_XML_INVALID.

### `date`

- **Output**
  - Nonempty `comment/@date` in structural/semantic.
- **OOXML**
  - Threaded comment dT.
- **Parsing**
  - Preserve the saved timestamp without conversion or reconstruction.

### `parent`

- **Output**
  - `comment/@parent` in both XML densities.
- **OOXML**
  - Source parentId matched to a known source ID, then rewritten to the generated ID.
- **Parsing**
  - Exclude missing/self/cyclic links and emit COMMENT_PARENT_INVALID for invalid
    targets or cycles. Preserve independently readable messages.

### `status`

- **Output**
  - `comment/@status="active|resolved|closed|unknown"`; plain uses the same vocabulary.
- **IR**
  - `ThreadedAnnotation.status: AnnotationStatus`.
- **OOXML**
  - done, default false for a readable modern comment.
- **Parsing**
  - 1/true/on → resolved; 0/false/off → active, case-insensitively.
  - Invalid values emit COMMENT_STATUS_INVALID and remain unknown.
  - The supported Excel completion field does not produce closed. Legacy notes
    have unknown status, rather than an invented active/resolved state.

### `cell`

- **Output**
  - `comment/@cell` and positional cell/comment-ref.
- **Parsing**
  - Use the original cell reference in the enclosing sheet. Do not infer a
    target from neighboring values or from comment text.

### `mentions`

- **Output**
  - Semantic direct `comment/mention/@person` children.
- **IR**
  - `ThreadedAnnotation.mentions`; only readable person names are retained.
- **Parsing**
  - Resolve explicit source people and emit each distinct display name once.
    Do not extract raw mention offsets, lengths or source person IDs into the
    reading model. See [mentions](mention.md).
