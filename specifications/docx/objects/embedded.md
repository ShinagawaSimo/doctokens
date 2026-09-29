# Embedded objects

[DOCX](../README.md) / Embedded objects

OLE content is represented by a type/name placeholder.

## Fields

### `type`

- **Output**
  - `embedded/@type`.

- **OOXML**
  - `w:object/o:OLEObject/@ProgID`

- **IR**
  - `InlineObject.embeddedType: str`

- **Parsing**
  - Lowercase ProgID; first substring mapping excel/word/powerpoint/acroexch/visio/paint/package → excel/word/powerpoint/pdf/visio/image/package.

- **Absence and defaults**
  - unknown.

### `progid`

- **Output**
  - Internal original identifier.

- **OOXML**
  - `o:OLEObject/@ProgID`

- **IR**
  - `InlineObject.progid: str`

- **Parsing**
  - Retain nonempty string; no OLE execution or nested package parse.

### `name`

- **Output**
  - `embedded/@name`.

- **OOXML**
  - First `v:shape` with @title or @alt, else first wp:docPr/@name.

- **IR**
  - `InlineObject.name: str`

- **Parsing**
  - First nonempty candidate in the stated order.

- **Absence and defaults**
  - Omitted.


## Source references

- [parse_embedded_object](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L140)
- [_progid_to_type](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L345)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L164)
