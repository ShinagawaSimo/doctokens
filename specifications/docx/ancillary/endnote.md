# Endnotes

[DOCX](../README.md) / Endnotes

Saved ancillary content is parsed independently of body layout.

## Processing

XML read failure: `ANCILLARY_XML_PARSE_FAILED`; omit the failed part. Skip source type separator and continuationSeparator. DTX includes the group in both XML densities. Plain appends referenced endnotes under `[Endnotes]` as `[ed<ID>: text]`.

## Fields

### `id`

- **Output**
  - `supplemental/endnotes/endnote/@id`.

- **OOXML**
  - `word/endnotes.xml/w:endnotes/w:endnote`; `@w:id`

- **IR**
  -  `AncillaryItem.id: str | None`

- **Parsing**
  - Copy nonempty source id; skip missing IDs.

### `locator`

- **Output**
  - `endnote/@locator`.

- **OOXML**
  - Derived from group and ID.

- **IR**
  - `AncillaryItem.loc: str`

- **Parsing**
  - `"endnotes." + id`.

### `text`

- **Output**
  - DTX `endnote` character data and inline elements.

- **OOXML**
  - `word/endnotes.xml/w:endnotes/w:endnote`

- **IR**
  - `AncillaryItem.text: str`

- **Parsing**
  - Join retained paragraph content with LF. Flatten table cells with ` | ` and rows with LF. Skip whitespace-only content without objects.

### `runs`

- **Output**
  - DTX inline semantics; DTP readable content.

- **OOXML**
  - `word/endnotes.xml/w:endnotes/w:endnote` child p/tbl/sdt/sdtContent/smartTag.

- **IR**
  - `AncillaryItem.runs: list[Run]`

- **Parsing**
  - Use the inline parser; insert separator runs between retained containers. Retain controls around their runs; tables have no table IR here.

### `rawHints`

- **Output**
  - Internal diagnostic detail.

- **OOXML**
  - `word/endnotes.xml/w:endnotes/w:endnote`

- **IR**
  - `AncillaryItem.rawHints: list[RawHint]`

- **Parsing**
  - Keep only if RAW_HINTS, include_raw_hints, and nonempty.


## Source references

- [AncillaryParser._parse_notes](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L100)
- [AncillaryParser._container_content](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L247)
- [_append_supplemental](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L319)
