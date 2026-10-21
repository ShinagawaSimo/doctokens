# Shapes

[PPTX](../README.md) / Shapes

Shape IDs are local to a slide. Output type depends on the retained content.

Explicit groups are retained as a compact `slide/groups` directory. Its ids are
slide-local `g1`, `g2`, ... in source traversal order. Only groups containing
retained source shapes and their ancestors are emitted. Grouping does not reorder
the source shape sequence or activate public geometry output.

## Processing

Retain textless shapes when they have alt, title, link, fromShape, or toShape; also retain any shape addressed by a retained connector. The name alone does not retain decoration.

## Fields

### `id`

- **Output**
  - Resource-bearing objects expose `@id` for resource lookup. Text and
    descriptive shapes use only `@shape-id`; no duplicate `@id` alias.

- **OOXML**
  - Shape-tree traversal.

- **IR**
  - `ShapeBlock.id: str`

- **Parsing**
  - After filtering and optional internal sorting, assign s1, s2, ...; rewrite connector endpoints. Object elements can replace this ID with their asset/chart/SmartArt ID.

### `type`

- **Output**
  - `p|title|textbox`, `img`, `table`, `chart`, `smartart`, `media`, or `shape`.

- **OOXML**
  - sp/pic/graphicFrame/media/cxnSp.

- **IR**
  - `ShapeBlock.type: str`

- **Parsing**
  - Dispatch by source local name; graphicFrame dispatches by graphicData/@uri.

- **Diagnostics**
  - `UNSUPPORTED_SHAPE_TYPE`, `GRAPHIC_FRAME_MISSING_DATA` skip unsupported frames/shapes.

### `shape-id`

- **Output**
  - `@shape-id` on every retained source shape's primary element in structural
    and semantic output, including text, pictures, tables, charts, SmartArt,
    standalone media and descriptive shapes.
- **IR**
  - `ShapeBlock.id: str`; the same compact slide-local id used by connectors.
- **Parsing**
  - Keep the existing per-slide allocation. This id is scoped by its slide and
    is not a document resource id. Resource-bearing elements separately expose
    image/table/chart/SmartArt/media resource ids through `@id`.
  - A picture's companion media element refers to the primary shape through
    `@owner-shape`; it does not create a second source shape or duplicate `shape-id`.
- **References**
  - Connector `from-shape`/`to-shape` identify `shape-id`, even when the target's
    `id` contains a resource id or the target's structural text has no `id`.

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

### `group`

- **Output**
  - Primary shape `@group` in both XML densities references its immediate group.
  - `groups/group/@parent` preserves nested containment and `@name` preserves a saved name.
- **IR**
  - `ShapeBlock.groups: list[ShapeGroup]` is the source ancestor path.
- **Parsing**
  - Preserve explicit `p:grpSp` containment. Do not infer groups from visual proximity.
