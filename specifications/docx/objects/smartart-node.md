# SmartArt nodes

[DOCX](../README.md) / SmartArt nodes

Node ordinals are 1-based positions in the retained label list.

## Fields

### `modelId`

- **Output**
  - Internal source key.

- **OOXML**
  - `dgm:pt/@modelId`

- **IR**
  - `SmartArtNode.modelId: str`

- **Parsing**
  - Required attribute access; a missing attribute causes enclosing SmartArt parse failure.

### `text`

- **Output**
  - Inline SmartArt text and resource node label.

- **OOXML**
  - Descendant a:t.

- **IR**
  - `SmartArtNode.text: str`

- **Parsing**
  - Concatenate then strip; omit empty node.

### `kind`

- **Output**
  - Resource node metadata.

- **OOXML**
  - `dgm:pt/@type`

- **IR**
  - `SmartArtNode.kind: str`

- **Parsing**
  - Copy nonempty string.


## Source references

- [parse_smartart_root](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L251)
