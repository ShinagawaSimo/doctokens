# Shared strings

[XLSX](../README.md) / Shared strings

The shared-string index is the source si ordinal.

## Fields

### `text`

- **Output**
  - Resolved cell display text.

- **OOXML**
  - xl/sharedStrings.xml/s:sst/s:si.

- **IR**
  - `list[str]` for a complete catalog; `dict[int, str]` for a selected catalog keyed by original si ordinals.

- **Parsing**
  - If direct t exists, use its text only. Otherwise concatenate direct r/t texts in order. Missing part → empty catalog.
  - Decode direct si children incrementally; clear and detach completed XML
    children. Retain the decoded catalog and requested rich runs, rather than
    the complete sharedStrings XML tree. Source ordinal and whitespace are unchanged.
  - Independent-cell default previews collect a safe superset of possible
    shared-string references during their worksheet extent preflight. Assemble
    and retain display/rich data only for those si ordinals. The SST XML is
    still scanned to its end, including unselected entries and any corrupt tail.
  - The reference prefix ends after a complete row reaches 500 mandatory
    non-residual cells. Internal saved blanks can make the rendered preview
    end earlier, so this prefix may conservatively include unused references.
    It never omits a string needed by the selected reading window.
  - Compatibility-path worksheets and plain previews with hidden columns use
    the complete catalog. If any selected sheet needs it, a multi-sheet parse
    uses a complete shared catalog. Explicit ranges, complete sessions and
    search/query paths currently retain their existing complete catalogs.

### `index`

- **Output**
  - Internal lookup position.

- **OOXML**
  - Cell t=s with v integer.

- **IR**
  - 0-based shared string index.

- **Parsing**
  - A complete catalog accepts only 0 <= index < len(strings). A selected catalog looks up the original ordinal directly, without renumbering it. Invalid integers, bounds or absent ordinals yield empty display text.
