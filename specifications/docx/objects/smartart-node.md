# SmartArt nodes

[DOCX](../README.md) / SmartArt nodes

Node ordinals are original one-based source-point positions, including retained empty endpoints.
Body preview and complete resource use the same `<node id="N">text</node>`.

## Fields

### `id`

- **Output**
  - Body/resource node id and explicit connection endpoint.

- **OOXML**
  - Original dgm:pt traversal ordinal; modelId is a temporary lookup key.

- **IR**
  - `SmartArtNode.id: int`

- **Parsing**
  - Missing modelId does not bind an edge. Duplicate keys bind to the first
    occurrence; independently retained nodes keep their original ordinals.
    Source keys are discarded after resolving connections. Neither the model
    nor resource output retains source IDs; filtered ID gaps are intentional.

### `text`

- **Output**
  - Inline SmartArt text and resource node label.

- **OOXML**
  - Descendant a:t.

- **IR**
  - `SmartArtNode.text: str`

- **Parsing**
  - Concatenate then strip; retain empty connected nodes and their graph roles. Body text
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
  - Keep kind on connected empty nodes as well as readable nodes. Standard
    types include node, asst (assistant), doc (root), pres, parTrans and sibTrans.
