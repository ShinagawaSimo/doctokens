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
  - Use the common [string reader](../../../packages/doctokens_excel/src/doctokens_excel/xlsx/parsing/modules/workbook/string_text.py) for shared si and inline is containers. Concatenate direct t and r/t text in source order; exclude phonetic-guide rPh text. Missing part → empty catalog.
  - Decode ST_Xstring `_xHHHH_` escapes once per source text node, before combining runs or applying text number formats. `_x005F_x0041_` becomes the literal `_x0041_`, not `A`. Combine adjacent escaped UTF-16 high/low surrogates into their Unicode scalar; `_xD83D__xDE00_` becomes `😀`. Preserve TAB/LF/CR and source spaces; do not decode the assembled cell or catalog value again.
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

- **Diagnostics**
  - XML 1.0 cannot contain some decoded controls/noncharacters or isolated surrogates. Replace each unrepresentable code unit/scalar with U+FFFD in reading text and report `XSTRING_CHARACTER_UNREPRESENTABLE`, naming the original U+code. A shared-string locator is `xl/sharedStrings.xml:si[N]` with the original zero-based ordinal; inline/cached string locators are `worksheet-part!cell`.
  - This safe text policy is not a lossless reconstruction of forbidden XML characters; the report retains their identity. Escaped literal sequences are preserved without a diagnostic. CR in DTX character data is serialized as `&#13;` so an XML reader cannot normalize it to LF.

### `index`

- **Output**
  - Internal lookup position.

- **OOXML**
  - Cell t=s with v integer.

- **IR**
  - 0-based shared string index.

- **Parsing**
  - A complete catalog accepts only 0 <= index < len(strings). A selected catalog looks up the original ordinal directly, without renumbering it. Invalid integers, bounds or absent ordinals yield empty display text.
