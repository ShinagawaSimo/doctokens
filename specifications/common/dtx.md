# DTX serialization

[COMMON](README.md) / DTX serialization

DTX 1.0 is one well-formed XML document. Empty elements may use XML self-closing syntax.

## Processing

```python
def element(name: str, text: str | None = None, /, **attrs: object | None) -> ET.Element:
    """Create one DTX element with normalized string attributes."""
    node = ET.Element(name)
    for key, value in sorted(attrs.items()):
        if value is not None:
            node.set(key.replace("_", "-"), _attribute_value(value))
    if text is not None:
        node.text = text
    return node
```

## Fields

### `root`

- **Output**
  - `document`, `presentation`, or `workbook`.

- **IR**
  - Format renderer root.

- **Parsing**
  - Root/format pairs: `(document, docx)`, `(presentation, pptx)`, `(workbook, xlsx)`.

### `density`

- **Output**
  - Root `@density="structural"` or `"semantic"`.

- **IR**
  - Selected density.

- **Parsing**
  - Public main renderer adds it; the lightweight XML validator does not itself validate this attribute.

### `format`

- **Output**
  - Root `@format`.

- **IR**
  - Format name.

- **Parsing**
  - Must match root element.

### `schema`

- **Output**
  - Root `@schema="doctokens-xml"`.

- **IR**
  - Constant.

- **Parsing**
  - Required on main DTX.

### `version`

- **Output**
  - Root `@version="1.0"`.

- **IR**
  - Constant.

- **Parsing**
  - Required on main DTX.

### `attributes`

- **Output**
  - Quoted XML attributes.

- **IR**
  - Serializer keyword arguments.

- **Parsing**
  - Sort attribute keys; replace `_` with `-`; omit `None`; serialize bool as lowercase `true/false`; other values via `str`. Empty strings are not universally omitted: each field defines its own filter.

### `text`

- **Output**
  - XML character data.

- **IR**
  - Python `str`.

- **Parsing**
  - Escape XML metacharacters. Text and tail preserve inline sequence; no generic trimming. Invalid XML characters can fail serialization validation.


## Source references

- [serialize](../../packages/ooxml_llm_core/src/ooxml_llm_core/doctokens_xml.py#L36)
- [validate_xml](../../packages/ooxml_llm_core/src/ooxml_llm_core/doctokens_xml.py#L43)
