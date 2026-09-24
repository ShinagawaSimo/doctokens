# Shapes

[PPTX](../README.md) / Shapes

Shape IDs are local to a slide. Output type depends on the retained content.

## Processing

Retain textless shapes when they have alt, title, link, fromShape, or toShape; also retain any shape addressed by a retained connector. The name alone does not retain decoration.

## Fields

### `id`

- **Output**
  - Semantic text `p|title/@id`; other shape elements also carry IDs in structural output.

- **OOXML**
  - Shape-tree traversal.

- **IR**
  - `ShapeBlock.id: str`

- **Parsing**
  - After filtering and optional internal sorting, assign s1, s2, ...; rewrite connector endpoints. Object elements can replace this ID with their asset/chart/SmartArt ID.

### `type`

- **Output**
  - `p|title`, `img`, `table`, `chart`, `smartart`, `media`, or `shape`.

- **OOXML**
  - sp/pic/graphicFrame/media/cxnSp.

- **IR**
  - `ShapeBlock.type: str`

- **Parsing**
  - Dispatch by source local name; graphicFrame dispatches by graphicData/@uri.

- **Diagnostics**
  - `UNSUPPORTED_SHAPE_TYPE`, `GRAPHIC_FRAME_MISSING_DATA` skip unsupported frames/shapes.

### `name`

- **Output**
  - Semantic `@name`.

- **OOXML**
  - First descendant cNvPr/@name.

- **IR**
  - `ShapeBlock.name: str`

- **Parsing**
  - Copy, default empty string; omit empty output attribute.

### `alt`

- **Output**
  - `shape/@alt`; picture alt in both XML densities.

- **OOXML**
  - cNvPr/@descr; picture fallback @title.

- **IR**
  - `ShapeBlock.alt: str`

- **Parsing**
  - Copy nonempty description. Descriptive textless shapes survive filtering if alt/title/link or resolved endpoints exist.

### `title`

- **Output**
  - `shape/@title` on descriptive shapes.

- **OOXML**
  - cNvPr/@title.

- **IR**
  - `ShapeBlock.title: str`

- **Parsing**
  - Copy nonempty value; chart titles are not transferred from ChartRecord to ShapeBlock.

### `kind`

- **Output**
  - `shape/@kind`.

- **OOXML**
  - prstGeom/@prst or connector status.

- **IR**
  - `ShapeBlock.kind: str`

- **Parsing**
  - Textless sp: preset geometry name, fallback shape. cxnSp: connector.

### `geometryType`

- **Output**
  - Internal preset name.

- **OOXML**
  - prstGeom/@prst.

- **IR**
  - `ShapeBlock.geometryType: str`

- **Parsing**
  - Copy when present; connector kind remains connector.

### `z`

- **Output**
  - Internal source stacking order.

- **OOXML**
  - Shape-tree visits.

- **IR**
  - `ShapeBlock.z: int`

- **Parsing**
  - Increment before parsing each candidate; unsupported/skipped shapes can leave gaps.


## Source references

- [SlideParser._descriptive_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L308)
- [SlideParser._filter_decorative_shapes](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L371)
- [SlideParser._renumber_shapes](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L395)
- [_shape_attrs](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L140)
