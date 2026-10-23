# Cell search

[XLSX](../README.md) / Cell search

find_cells is a literal search over retained session data.

## Display-text location

### `find_text(query, options=..., sheets=...)`

- **Output**
  - [TextSearchResult](../../common/text-search.md), with exact `sheet` and
    single-cell `range_spec` locators. Search displayed cell text, not formulas,
    annotations or names. Merged shadow cells do not duplicate an anchor hit.
- **Source**
  - Saved cells in requested sheet order, then row/column order. `sheets=None`
    searches all parsed sheets; an empty list searches none. Unknown names fail.
- **Processing**
  - The session method reuses its parsed workbook. Standalone
    `find_xlsx_text(source, query, options=..., search_options=..., sheets=...)`
    owns a structural parse restricted to explicit sheets; it closes the reader
    and returns bounded search values without creating a reusable full session.
    Output bounds do not promise early XML termination or constant memory.
  - `options` on the standalone call means `ParseOptions`; `search_options`
    means `TextSearchOptions`. On a session, `options` means TextSearchOptions.
    Neither entry evaluates formulas or normalizes displayed strings.

## Fields

### `query`

- **Output**
  - Search term.

- **Source**
  - Call argument.

- **IR**
  - `str`

- **Parsing**
  - Regex-escape query and perform case-sensitive substring matching. Empty query returns a complete workbook containing an empty `matches` element.

### `sheets`

- **Output**
  - Search order.

- **Source**
  - Call argument.

- **IR**
  - `list[str] | None`

- **Parsing**
  - None or empty → all parsed sheets in order; unknown sheet → KeyError.

### `kind`

- **Output**
  - Search field.

- **Source**
  - Call argument.

- **IR**
  - `str | None`

- **Parsing**
  - None searches value, formula, legacy comment, hyperlink in that priority; return at most one match per cell. definedName is also searched after each sheet. Threaded comments and rich descriptors are not searched.

### `limit`

- **Output**
  - Maximum matches.

- **Source**
  - Call argument.

- **IR**
  - `int = 50`

- **Parsing**
  - Stop when match count reaches limit; zero/negative yields no matches.

### `text`

- **Output**
  - Complete `<workbook density="structural" format="xlsx"><matches><match ...>text</match></matches></workbook>`.

- **Source**
  - Matched retained fields.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - Cell matches include quoted `cell="Sheet!A1"` and `field="value|formula|comment|hyperlink"` attributes. Defined-name matches use `field="definedName"` and `name = ref` text. All elements close; XML text and attributes are escaped. `syntax_version=doctokens-xml/1.0`, `media_type=application/xml`, `density=structural`.
