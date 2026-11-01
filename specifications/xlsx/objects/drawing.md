# Drawing anchors and native objects

[XLSX](../README.md) / Drawing anchors

Read explicit drawing relationships on worksheets and chart sheets. Visible text
comes from saved DrawingML text bodies; no position-based business relationships,
font reconstruction or rendering are performed.

## Processing

The [drawing reader](../../../packages/doctokens_excel/src/doctokens_excel/xlsx/parsing/modules/worksheets/drawings.py)
reads each distinct related drawing part once, with its own relationship map.
Traverse source anchor order, including twoCellAnchor, oneCellAnchor and
absoluteAnchor. Visit groups recursively; pictures and charts retain their own
resource IDs. Native text boxes/shapes, groups, explicit connectors and
unreadable objects have a separate workbook-scoped shapeN identity.

Only explicit Fallback children of drawing AlternateContent are used on this
spreadsheet path. An unavailable representation retains a placeholder;
this is not the PowerPoint capability selector. Unsupported producer extensions
are not interpreted by merely matching a local element name.

## Fields

### `ref`

- **Output**
  - Image/chart/textbox/shape anchor reference when saved.
- **OOXML**
  - xdr:from/xdr:col and xdr:row, where
    xdr=`http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing`.
- **IR**
  - DrawingImage/DrawingChart/DrawingShape.ref.
- **Parsing**
  - Convert zero-based integer column/row to A1. Missing from, including an
    absoluteAnchor, retains no invented cell association. Invalid/out-of-bounds
    coordinates emit DRAWING_ANCHOR_INVALID and leave the reference empty,
    preserving independently readable object text.
  - Range relevance privately retains the saved twoCellAnchor from/to rectangle;
    objects can intersect a request with their start cell outside. Include
    endpoint cells conservatively without calculating pixel coverage.
    oneCellAnchor uses its start cell; EMU extents are not converted to guessed
    grid coordinates. An absolute/unreadable anchor cannot establish irrelevance
    and remains visible. The private footprint is not serialized.

### `id`

- **Output**
  - textbox/shape/drawing-group/@id; unsupported drawing/@id.
- **OOXML**
  - Retained drawing traversal, separate from source cNvPr IDs.
- **IR**
  - `DrawingShape.id: str` in model/drawing.py.
- **Parsing**
  - Allocate shape1, shape2, ... across parsed sheets. Source IDs are resolved
    within each drawing part; equal source IDs in another part do not collide.
    Images/charts use their existing imageN/chartN resource namespaces.

### `text`

- **Output**
  - Both XML densities use textbox/p paragraphs; plain includes native text
    after the existing compact image/chart summaries.
- **OOXML**
  - xdr:sp/xdr:txBody/a:p with a:r/a:t, a:fld/a:t, a:br and a:tab.
- **IR**
  - DrawingShape.text and paragraphs.
- **Parsing**
  - Preserve paragraph/soft-break boundaries, spaces, saved field text and
    directly readable native equations. Do not recalculate fields or infer
    text from images. Character typography is outside this text-recovery scope.
  - Example: a textbox containing 仅供内部 at D4 becomes
    `<textbox id="shape1" ref="D4"><p>仅供内部</p></textbox>`.
  - Unknown inline content preserves a visible unreadable-content marker and
    DRAWING_TEXT_UNSUPPORTED rather than silently concatenating its neighbors.

### `alt`

- **Output**
  - Shape/textbox @alt; pictures follow [image descriptions](image.md).
    Plain describes textless objects with saved alternative text.
- **OOXML**
  - The object's own xdr:cNvPr/@descr.
- **Parsing**
  - Keep the saved description with its owning object. Do not reuse another
    object's description or nearby worksheet-cell text.

### `title`

- **Output**
  - Shape/textbox @title.
- **OOXML**
  - The object's own xdr:cNvPr/@title.
- **Parsing**
  - Retain an explicit nonempty title.

### `group`

- **Output**
  - @group on the immediate member; drawing-group records provide group IDs,
    names and parent group references.
- **OOXML**
  - xdr:grpSp nesting.
- **IR**
  - DrawingShape/DrawingImage/DrawingChart.group.
- **Parsing**
  - Preserve saved membership. Omit empty decorative groups unless their own
    description/action or a retained connector gives them reading significance.
    Group coordinates do not imply a semantic connection.

### `name`

- **Output**
  - Optional drawing-group/@name in both XML densities. Ordinary shape names
    remain internal; their readable text, alt and title have separate fields.
- **OOXML**
  - The group's own xdr:cNvPr/@name.
- **Parsing**
  - Omit only a complete case-sensitive `Group [1-9][0-9]*` name with one ASCII
    space on an actual group. Keep other names verbatim, including Chinese,
    unknown prefixes, incompatible object types and leading-zero suffixes.
  - Do not compare the suffix with the source cNvPr ID. IDs, parent references
    and member relationships remain unchanged. This heuristic also omits an
    authored name that deliberately matches; a retained name is not proof of
    authored provenance. No new name inspection API is implied.
- **References**
  - [Excel Shape.Name](https://learn.microsoft.com/en-us/office/vba/api/excel.shape.name)
    does not specify a complete automatic prefix catalog. Group is a confirmed
    English producer convention, not a universal rule for Excel object names.

### `link`

- **Output**
  - Shape/textbox @link.
- **OOXML**
  - cNvPr/a:hlinkClick/@r:id and that drawing part's relationship map.
- **Parsing**
  - Copy the explicit target; do not fetch external content.

### `fromShape`

- **Output**
  - Connector shape/@from-shape.
- **OOXML**
  - a:stCxn/@id.
- **Parsing**
  - Resolve only against explicit source shape IDs in the same drawing part,
    including pictures and charts. Do not infer from proximity.

### `toShape`

- **Output**
  - Connector shape/@to-shape.
- **OOXML**
  - a:endCxn/@id.
- **Parsing**
  - The same exact source-identity resolution as fromShape. A referenced
    otherwise decorative endpoint remains available.

### `unparsed`

- **Output**
  - `<unsupported type="drawing" source="SOURCE" id="shapeN"/>`;
    plain `[Unparsed drawing: SOURCE]`. Failed image/chart content remains
    attached to its existing resource-bearing object with an unsupported child.
- **Diagnostics**
  - DRAWING_PART_MISSING, DRAWING_XML_INVALID, DRAWING_ROOT_UNSUPPORTED,
    DRAWING_RELS_XML_INVALID, DRAWING_OBJECT_UNSUPPORTED, DRAWING_IMAGE_MISSING.
- **Parsing**
  - A known unreadable element/part retains its existence. Readable fallback
    content is emitted once; explicit empty fallback content stays empty.
    Invalid position/default-value fallback does not add an element marker.
    Existing cell search/query contracts do not index generated markers or
    drawing text.
