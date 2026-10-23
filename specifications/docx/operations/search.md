# Text search

[DOCX](../README.md) / Text search

## Fields

### `find_text(query, options=..., include_headers_footers=False)`

- **Output**
  - [TextSearchResult](../../common/text-search.md).
- **Source**
  - Retained body blocks and their nested textbox/table blocks, then footnotes,
    endnotes and comments; opt-in headers and footers follow.
- **Processing**
  - Read native paragraph text across runs, respecting the pinned revision view.
    Each table cell contributes its first matching paragraph. Locate using
    saved-page hints and block/table/textbox IDs, without re-rendering pages.
    A paragraph spanning hints returns its saved page interval.
  - Ancillary paragraphs retain source boundaries and one-based table/cell
    positions, including soft line breaks within a paragraph. Note/comment references give
    an anchor when known; unanchored stories return their source/item locator.
    No layout-derived page is guessed for headers or footers.
