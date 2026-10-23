# Text search

[PPTX](../README.md) / Text search

## Fields

### `find_text(query, options=...)`

- **Output**
  - [TextSearchResult](../../common/text-search.md).
- **Source**
  - Slides in presentation order, shapes in retained source order, and individual
    paragraphs or table cells; then saved notes and slide-linked comments.
- **Processing**
  - Match paragraph text across runs; do not search serialized list/shape fields
    or concatenate distinct paragraphs. Notes/comments use retained line units.
    Hidden slides remain searchable with the same saved slide numbers.
  - Locators carry slide_start and a source, with shape_id, paragraph, table_id,
    one-based row/column or comment item_id when applicable.
