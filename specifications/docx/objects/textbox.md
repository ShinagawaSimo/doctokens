# Text boxes

[DOCX](../README.md) / Text boxes

Text boxes retain their reading structure through the existing paragraph and
table parsers. DrawingML and VML bind the outer object separately from its content.

## Fields

### `text`

- **Output**
  - XML contains paragraphs/headings, tables and inline content inside `textbox`.
    Plain output keeps readable text and tab-separated table cells, including empty cells.

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
