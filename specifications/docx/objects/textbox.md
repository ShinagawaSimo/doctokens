# Text boxes

[DOCX](../README.md) / Text boxes

Text boxes preserve readable text without an internal paragraph/table tree.

## Fields

### `text`

- **Output**
  - `<textbox>text<br/>...</textbox>`; plain readable text.

- **OOXML**
  - `w:txbxContent` under DrawingML or VML.

- **IR**
  - `InlineObject.text: str`

- **Parsing**
  - For each direct child, collect descendant t/tab/br/cr; separate retained blocks with LF. Tables join nonempty stripped cells with ` | `. Skip whitespace-only textboxes.

### `alt`

- **Output**
  - Semantic `textbox/@alt`.

- **OOXML**
  - Drawing metadata.

- **IR**
  - `InlineObject.alt: str`

- **Parsing**
  - Copy drawing alt; structural omits it.


## Source references

- [_textbox_objects_from_nodes](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L192)
- [_container_plain_text](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L307)
- [_table_plain_text](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L322)
