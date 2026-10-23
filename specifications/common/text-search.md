# Bounded text search

[Common](README.md) / Text search

`TextSearchOptions`, `TextMatch`, and `TextSearchResult` are exported by
`ooxml_llm_core`. Format sessions expose `find_text(query, options=...)`.
Results are search values, not a density rendering or a `ParseResult`.

## Fields

### `query`

- **Source**
  - Caller string, 1–4,000 Unicode characters.
- **Processing**
  - Literal substring matching; regular-expression metacharacters are escaped.
    Match text across runs within one retained paragraph. Do not join separate
    paragraphs, cells, or objects to create a match. Source paragraphs omit
    synthesized list-prefix runs. Generated XML, image/OCR text, chart caches
    and unresolved embedded contents are not searched.
  - Return one result per matching paragraph or table/spreadsheet cell, using
    the first occurrence. For a cell containing separate paragraphs, use its
    first matching paragraph without joining the paragraphs.

### `case_sensitive`

- **Default**
  - `True`.
- **Processing**
  - `False` uses Python Unicode regular-expression case-insensitive literal
    matching. No whitespace, accent, or Unicode normalization is performed.

### `offset` and `limit`

- **Default**
  - Skip zero matching units; return at most 20. Maximum limit: 200.
- **Processing**
  - Offset is a nonnegative integer count of matching paragraphs/cells, not a
    character position. Scan in format source order, skip the requested count,
    and inspect at most one additional matching unit to determine continuation.
    Do not calculate a full total. Overshooting the last match returns empty
    matches and no continuation. Booleans are not integer arguments.

### `context_before` and `context_after`

- **Default**
  - 80 Unicode characters on each side of the first match.
- **Processing**
  - Independently configurable integers from 0 to 4,000. Always retain the
    complete match, bounded by the paragraph/cell text. Prefix/suffix `…` marks
    omitted context; offsets are not returned as if this were full text.

### `matches`

- **Output**
  - Tuple of `TextMatch(text, locator)` values. Each `text` is a plain excerpt;
    `locator` contains format-specific source coordinates.
- **Processing**
  - Search respects the session's pinned parse options, including DOCX revision
    view. Returned locators are independent dictionaries. A closed session
    rejects subsequent searches. Bounds limit results, not initial parsing cost.

### `next_offset`

- **Output**
  - Next matching-unit offset when another match exists; otherwise `None`.
- **Processing**
  - Continue using the same snapshot, query, case mode, scope and limit. Context
    lengths may change without changing which units match. Character fragments
    of a single tool response use the separate result transport.
