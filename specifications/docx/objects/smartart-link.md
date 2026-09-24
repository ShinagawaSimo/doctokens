# SmartArt links

[DOCX](../README.md) / SmartArt links

Connections address retained node ordinals.

## Fields

### `from`

- **Output**
  - Resource source ordinal.

- **OOXML**
  - `dgm:cxn/@srcId`

- **IR**
  - `SmartArtLink["from"]: int`

- **Parsing**
  - Resolve modelId to retained 1-based node position; omit connection if unresolved.

### `to`

- **Output**
  - Resource destination ordinal.

- **OOXML**
  - `dgm:cxn/@destId`

- **IR**
  - `SmartArtLink["to"]: int`

- **Parsing**
  - Resolve by the same map; omit connection if unresolved.

### `kind`

- **Output**
  - Resource relation type.

- **OOXML**
  - `dgm:cxn/@type`

- **IR**
  - `SmartArtLink.kind: str`

- **Parsing**
  - Copy nonempty value.


## Source references

- [parse_smartart_root](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L251)
