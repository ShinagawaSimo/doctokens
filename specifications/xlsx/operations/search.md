# Cell search

[XLSX](../README.md) / Cell search

find_cells is a literal search over retained session data.

## Fields

### `query`

- **Output**
  - Search term.

- **Source**
  - Call argument.

- **IR**
  - `str`

- **Parsing**
  - Regex-escape query and perform case-sensitive substring matching. Empty query returns `<matches>
  - `.

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
  - `<matches>` followed by `<match ...>text` records.

- **Source**
  - Matched retained fields.

- **IR**
  - `ParseResult.text`

- **Parsing**
  - Cell matches include quoted `cell="Sheet!A1"` and bare field attribute; defined-name matches include name = ref. No closing match/matches tags. Escape text with html.escape; syntax_version=legacy-markup/0, media_type=text/plain.


## Source references

- [XlsxReadSession.find_cells](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L225)
- [_find_cells](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L379)
- [_cell_match](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L420)
