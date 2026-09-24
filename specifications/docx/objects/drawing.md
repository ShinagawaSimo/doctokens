# Drawing metadata

[DOCX](../README.md) / Drawing metadata

Metadata is attached to the objects found in a drawing subtree.

## Processing

Emit chart references, then SmartArt references, then the first embedded-image reference, then nonempty textboxes. If nothing resolves, retain one drawing placeholder. This grouping is not a reconstruction of arbitrary drawing descendant order.

## Fields

### `placement`

- **Output**
  - Internal; no geometry attribute in DTX.

- **OOXML**
  - `wp:inline`, `wp:anchor`, or `w:pict`.

- **IR**
  - `DrawingCommon.placement: str`

- **Parsing**
  - Choose the first inline container, otherwise the first anchor/container candidate; fallback drawing. VML uses vml.

### `name`

- **Output**
  - Fallback semantic image alternative text; embedded name uses separate rules.

- **OOXML**
  - `wp:docPr/@name`; VML `v:shape/@id`.

- **IR**
  - `DrawingCommon.name: str`

- **Parsing**
  - Copy nonempty value.

### `alt`

- **Output**
  - Semantic img/textbox alt.

- **OOXML**
  - `wp:docPr/@descr`; VML `v:shape/@alt`.

- **IR**
  - `DrawingCommon.alt: str`

- **Parsing**
  - Copy nonempty value. Drawing placeholder fallback is `alt or title or name`.

### `title`

- **Output**
  - Chart title can be overwritten by drawing title.

- **OOXML**
  - `wp:docPr/@title`

- **IR**
  - `DrawingCommon.title: str`

- **Parsing**
  - Copy after referenced chart/SmartArt fields; ordinary images do not emit a title attribute.

### `cx`

- **Output**
  - Internal extent only.

- **OOXML**
  - First extent with @cx in selected container.

- **IR**
  - `DrawingCommon.cx: str`

- **Parsing**
  - Keep source string; no unit conversion or layout.

### `cy`

- **Output**
  - Internal extent only.

- **OOXML**
  - Same extent @cy.

- **IR**
  - `DrawingCommon.cy: str`

- **Parsing**
  - Keep source string.


## Source references

- [DrawingScanResult.scan](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L31)
- [drawing_objects](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L88)
- [pict_objects](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L119)
