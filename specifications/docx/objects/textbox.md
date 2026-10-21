# Text boxes

[DOCX](../README.md) / Text boxes

Text boxes retain their reading structure through the existing paragraph and
table parsers. DrawingML and VML bind the outer object separately from its content.

## Fields

### `text`

- **Output**
  - XML contains paragraphs/headings, tables and inline content inside `textbox`.
    Floating text boxes are independent stories following their owning paragraph;
    an empty `textbox-ref` at the source anchor links to their id. Actual inline
    text boxes remain inside the original inline sequence.
  - Plain output keeps readable text and tab-separated table cells, including
    empty cells. Floating references and labelled stories follow the complete
    owning paragraph, so their contents do not interrupt its prose.

- **OOXML**
  - `w:txbxContent` under DrawingML or VML.

- **IR**
  - `InlineObject.text: str`

- **Parsing**
  - A fallback summary is derived from parsed blocks. Public document parsing uses
    the retained block tree for output, so links, numbering, revisions, controls
    and nested images do not depend on the summary string.
  - Omit an empty story after revision/content filtering; never substitute its
    unfiltered source text when the selected revision view removes the contents.

### `blocks`

- **Output**
  - Source-order block structure in both XML densities. Formatting follows the
    selected density; nested image ids and table ids remain addressable.
- **OOXML**
  - `w:txbxContent` paragraphs, tables and block content controls.
- **IR**
  - `InlineObject.blocks: list[Block]`.
- **Parsing**
  - Use a separate inline field stack and numbering-counter story. Nested story
    page breaks do not advance the enclosing body's page state.
  - Share document block/table id allocators and bookmark/comment registration;
    use the actual owning part for relationships. Nested table resources appear
    in the session resource directory, including stories in retained ancillary parts.
  - DrawingML scanning stops at text-box content so nested images/charts are not
    also emitted as outer drawing objects.
- **Diagnostics**
  - `UNSUPPORTED_STORY_CHILD` for unhandled block-container children.
  - `TEXTBOX_NESTING_LIMIT` when nesting exceeds 32 stories; no silent fallback
    to unfiltered descendant text.

### `alt`

- **Output**
  - Semantic `textbox/@alt`.

- **OOXML**
  - Drawing metadata.

- **IR**
  - `InlineObject.alt: str`

- **Parsing**
  - Copy drawing alt; structural omits it.

### `id`

- **Output**
  - Both XML densities: floating `textbox/@id` and matching `textbox-ref/@id`.
    Plain uses one `[Textbox]` label per story immediately after the owning
    paragraph, with no duplicate id or reference list. XML retains explicit ids
    because they identify the source anchor relationship.
- **OOXML**
  - Owning part, source paragraph allocator id and retained floating-object ordinal.
- **IR**
  - `InlineObject.id: str`.
- **Parsing**
  - Assign `tb-{block_id}-{ordinal}` in `word/document.xml`; elsewhere include
    `{part}-` before the block id. Ordinals start at 1 per source paragraph.
    Treat ids as opaque values. Nested stories use their own paragraph ids.
  - Assign before page selection. Reusing a parsed snapshot does not change ids
    across densities or windows. A window includes a story only when the source
    anchor/reference is selected; do not copy it to every continuation fragment.

### `placement`

- **Output**
  - Controls inline versus independent-story projection; not a visual layout claim.
- **OOXML**
  - DrawingML `wp:anchor` versus `wp:inline`; VML shape `style` position.
- **IR**
  - `InlineObject.placement`.
- **Parsing**
  - `anchor` is floating. VML `position:absolute` or `position:relative`, ignoring
    case and surrounding whitespace, is also floating. Unknown VML placement and
    malformed drawings without an explicit anchor retain the inline fallback.
  - Preserve source anchors without guessing an image/caption relationship from
    proximity. A floating story follows its complete owning source paragraph;
    inline page milestones can remain inside that paragraph in XML. Definitions
    follow source anchor order and are not reordered by visual position.
