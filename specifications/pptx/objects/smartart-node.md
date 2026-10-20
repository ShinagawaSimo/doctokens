# SmartArt nodes

[PPTX](../README.md) / SmartArt nodes

The source modelId is used only during graph resolution.

## Fields

### `id`

- **Output**
  - Resource node ordinal.

- **OOXML**
  - pt encounter order.

- **IR**
  - `SmartArtNode.id: int`

- **Parsing**
  - len(nodes)+1; map source modelId (default empty) to this ordinal, replacing duplicate keys.

### `text`

- **Output**
  - DTX inline label / resource node text.

- **OOXML**
  - Descendant local-name t.

- **IR**
  - `SmartArtNode.text: str`

- **Parsing**
  - Concatenate text including empty/whitespace results.
