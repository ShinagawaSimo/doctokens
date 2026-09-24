# Headers

[DOCX](../README.md) / Headers

Saved ancillary content is parsed independently of body layout.

## Processing

XML read failure: `ANCILLARY_XML_PARSE_FAILED`; omit the failed part. Scan matching package names in lexical order, including parts not referenced by a section. This is a part inventory, not a mapping of headers/footers to physical pages. Only semantic output includes this group.

## Fields

### `id`

- **Output**
  - `supplemental/headers/header/@id`.

- **OOXML**
  - `word/header*.xml`; package basename without .xml

- **IR**
  -  `AncillaryItem.id: str | None`

- **Parsing**
  - Use basename (e.g. header1).

### `locator`

- **Output**
  - `header/@locator`.

- **OOXML**
  - Derived from group and ID.

- **IR**
  - `AncillaryItem.loc: str`

- **Parsing**
  - `"headers." + id`.

### `text`

- **Output**
  - DTX `header` character data and inline elements.

- **OOXML**
  - `word/header*.xml`

- **IR**
  - `AncillaryItem.text: str`

- **Parsing**
  - Join retained paragraph content with LF. Flatten table cells with ` | ` and rows with LF. Skip whitespace-only content without objects.

### `runs`

- **Output**
  - DTX inline semantics; DTP readable content.

- **OOXML**
  - `word/header*.xml` child p/tbl/sdt/sdtContent/smartTag.

- **IR**
  - `AncillaryItem.runs: list[Run]`

- **Parsing**
  - Use the inline parser; insert separator runs between retained containers. Retain controls around their runs; tables have no table IR here.

### `rawHints`

- **Output**
  - Internal diagnostic detail.

- **OOXML**
  - `word/header*.xml`

- **IR**
  - `AncillaryItem.rawHints: list[RawHint]`

- **Parsing**
  - Keep only if RAW_HINTS, include_raw_hints, and nonempty.


## Source references

- [AncillaryParser._parse_header_footer](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L85)
- [AncillaryParser._container_content](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/ancillary/parts.py#L247)
- [_append_supplemental](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L319)
