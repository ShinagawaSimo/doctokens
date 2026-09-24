# SmartArt links

[PPTX](../README.md) / SmartArt links

Edges reference retained node ordinals.

## Fields

### `from`

- **Output**
  - Resource source.

- **OOXML**
  - cxn/@fromModelId.

- **IR**
  - `SmartArtLink["from"]: int`

- **Parsing**
  - Resolve prior modelId map; unresolved connection is omitted.

### `to`

- **Output**
  - Resource destination.

- **OOXML**
  - cxn/@toModelId.

- **IR**
  - `SmartArtLink["to"]: int`

- **Parsing**
  - Same prior-node resolution.


## Source references

- [EmbeddedObjectExtractor._parse_diagram_data](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/resources/objects.py#L295)
