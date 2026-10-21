# Drawing metadata

[DOCX](../README.md) / Drawing metadata

Metadata is attached to the objects found in a drawing subtree.

## Processing

DrawingML emits chart references, then SmartArt references, then the first embedded-image reference, then nonempty textboxes. If nothing resolves, retain one drawing placeholder. This grouping is not a reconstruction of arbitrary DrawingML descendant order.

VML `w:pict` emits image references and nonempty textboxes in source order.
Each shape owns its description, so a later shape cannot overwrite an earlier
image or text box's metadata. An image with an unresolved or missing `r:id`
retains a drawing placeholder without an id; other objects remain readable.
Text-box contents retain paragraph/table structure. A pict with no emitted
image or nonempty text box retains one drawing placeholder.

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
  - `wp:docPr/@name`; owning VML shape `@id`.

- **IR**
  - `DrawingCommon.name: str`

- **Parsing**
  - Copy nonempty value.

### `alt`

- **Output**
  - Semantic img/textbox alt.

- **OOXML**
  - `wp:docPr/@descr`; owning VML shape `@alt`.

- **IR**
  - `DrawingCommon.alt: str`

- **Parsing**
  - Copy nonempty value. Drawing placeholder fallback is `alt or title or name`.

### `title`

- **Output**
  - Chart title can be overwritten by drawing title.

- **OOXML**
  - `wp:docPr/@title`; owning VML shape `@title` and `v:imagedata/@o:title`.

- **IR**
  - `DrawingCommon.title: str`

- **Parsing**
  - Copy after referenced chart/SmartArt fields; ordinary images do not emit a title attribute.
  - VML shape @title and imagedata/@o:title participate in the image alt fallback; see [images](image.md).

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
