# Shapes

[PPTX](../README.md) / Shapes

Shape IDs are local to a slide. Output type depends on the retained content.

Explicit groups are retained as a compact `slide/groups` directory. Its ids are
slide-local `g1`, `g2`, ... in source traversal order. Only groups containing
retained source shapes and their ancestors are emitted. Grouping does not reorder
the source shape sequence or activate public geometry output.

## Processing

Retain textless shapes when they have alt, title, link, fromShape, or toShape;
also retain shapes addressed by a retained connector or an exact modern comment
anchor. The name alone does not retain decoration.

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
  - `p|title|textbox`, `img`, `table`, `chart`, `smartart`, `media`, `shape`,
    or `unsupported`.

- **OOXML**
  - sp/pic/graphicFrame/media/cxnSp.

- **IR**
  - `ShapeBlock.type: str`

- **Parsing**
  - Dispatch by source local name; graphicFrame dispatches by graphicData/@uri.

- **Diagnostics**
  - Unsupported source shapes and frames or failed object dispatch retain
    `<unsupported type="shape" source="SOURCE_NAME" shape-id="sN"/>` and their
    existing diagnostics. Plain emits `[Unparsed shape: SOURCE_NAME]`.
    Shape-tree property/extension containers do not represent independent
    visible elements and produce no placeholders.

### `AlternateContent`

- **Output**
  - Exactly one selected representation in the original shape/group position.
    No readable representation yields an unsupported shape with
    `source="AlternateContent"` and SHAPE_ALTERNATE_CONTENT_UNSUPPORTED.
- **OOXML**
  - mc:AlternateContent directly inside p:spTree or p:grpSp, including nested
    choices and groups.
- **Parsing**
  - Resolve Choice/@Requires in the original namespace scope. The first
    supported and readable Choice wins; otherwise use an explicit readable
    Fallback. Unknown, unbound and locally rebound requirements are rejected.
  - Supported requirement namespaces are PresentationML, DrawingML/main,
    ChartML, DiagramML, Office Math, DrawingML 2010, PowerPoint 2010 and ChartEx.
    Branch content must also be readable: sp, pic, cxnSp, grpSp or a graphicFrame
    with a supported table/chart/ChartEx/diagram/OLE URI. A namespace alone does
    not establish support for unknown content such as p:contentPart.
  - Recurse through nested alternatives and group content. Rejected branches
    produce neither text nor diagnostics from their descendants. A selected
    empty branch remains empty; it does not imply decoding failure. A readable
    fallback already represents the element and gets no extra placeholder.
  - Alias prefixes are supported. Source order, group ownership, connector IDs
    and inherited defaults use the selected tree. No rendering or OLE execution
    is performed to recover text from an unreadable representation.

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
  - Semantic shape `@name`; group directory `@name` in both XML densities.
    Plain omits object names.

- **OOXML**
  - First descendant cNvPr/@name.

- **IR**
  - `ShapeBlock.name: str`

- **Parsing**
  - Preserve nonempty names except the exact English default-name forms below.
    Match the complete prefix, one ASCII space, and a canonical positive ASCII
    integer (`[1-9][0-9]*`). Matching is case-sensitive. Do not compare the
    numeric suffix with cNvPr/@id.
  - Require a PresentationML object with PresentationML cNvPr. Compatible
    prefixes are Group for grpSp, Picture for pic, and Chart/Table/Diagram for
    graphicFrame with the corresponding recognized graphicData URI (including
    ChartEx for Chart).
  - For sp/cxnSp geometry: rect permits Rectangle, roundRect permits Rounded
    Rectangle, ellipse permits Oval, and line permits Line. A line cxnSp also
    permits Straight Connector. An sp with preset/custom geometry permits
    AutoShape; custom geometry also permits Freeform. An sp with txBody and
    absent/rect geometry permits Text Box and TextBox.
  - A declared ph permits Placeholder. Its direct or inherited title/ctrTitle
    role also permits Title; sldNum permits Slide Number Placeholder.
  - Chinese names, unknown prefixes, incompatible types, leading-zero suffixes
    and other nonmatches remain verbatim. This is a conservative heuristic,
    not proof that retained names were authored by a person. A manually assigned
    matching name is also omitted. Shape text, descriptions and titles are
    outside this filter; names alone still do not retain decorative shapes.
- **References**
  - [PowerPoint Shape.Name](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.shape.name)
    specifies automatic ShapeType Number names and advises custom names to
    avoid that form; examples include Placeholder 1, Oval 2 and Rectangle 3.
  - [OOXML non-visual drawing properties](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.presentation.nonvisualdrawingproperties?view=openxml-3.0.1)
    define a non-unique Object Model-compatible name, without an authored-name
    provenance flag. Other English prefixes above cover confirmed producer
    conventions rather than a universal normative prefix catalog.

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
  - `groups/group/@parent` preserves nested containment; `@name` follows the
    name-filtering rule above. Filtering a name does not change group IDs,
    parents or membership.
- **IR**
  - `ShapeBlock.groups: list[ShapeGroup]` is the source ancestor path.
- **Parsing**
  - Preserve explicit `p:grpSp` containment. Do not infer groups from visual proximity.
