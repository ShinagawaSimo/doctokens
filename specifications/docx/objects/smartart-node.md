# SmartArt nodes

[DOCX](../README.md) / SmartArt nodes

Node ordinals are one-based source-point positions, including empty nodes.
Body preview and complete resource use the same `<node id="N">text</node>`.

## Fields

### `modelId`

- **Output**
  - Internal source key.

- **OOXML**
  - `dgm:pt/@modelId`

- **IR**
  - `SmartArtNode.modelId: str`

- **Parsing**
  - Missing modelId defaults to empty and does not bind an edge. Duplicate keys
    bind to the first occurrence; independently retained nodes keep their ordinals.

### `text`

- **Output**
  - Inline SmartArt text and resource node label.

- **OOXML**
  - Descendant a:t.

- **IR**
  - `SmartArtNode.text: str`

- **Parsing**
  - Concatenate then strip; retain empty nodes and their graph roles. Body text
    can be previewed under the SmartArt budget; resource text remains complete.

### `kind`

- **Output**
  - Body/resource node metadata.

- **OOXML**
  - `dgm:pt/@type`

- **IR**
  - `SmartArtNode.kind: str`

- **Parsing**
  - Copy nonempty string.
