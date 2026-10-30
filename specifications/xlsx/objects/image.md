# Drawing images

[XLSX](../README.md) / Drawing images

Images are referenced by package location without eager binary reads.

## Fields

### `id`

- **Output**
  - img/@id.

- **OOXML**
  - Each native xdr:pic and its a:blip embedded or linked relationship.

- **IR**
  - `DrawingImage.id: str`

- **Parsing**
  - image1,image2,... across accepted worksheet/chart-sheet objects.
    Grouped pictures are independent occurrences.

### `ref`

- **Output**
  - img/@ref.

- **OOXML**
  - Drawing start anchor.

- **IR**
  - `str`

- **Parsing**
  - See [anchors](drawing.md).

### `alt`

- **Output**
  - img/@alt in both XML densities; included in the plain image description.

- **OOXML**
  - That picture's own xdr:cNvPr/@descr, otherwise its @title.

- **IR**
  - `str`

- **Parsing**
  - Preserve the saved nonempty description; never substitute an unrelated
    shape's text. If @title is also saved and differs, retain img/@title.

### `part`

- **Output**
  - Resource package part.

- **OOXML**
  - Resolved blip relationship target.

- **IR**
  - `str`

- **Parsing**
  - Require an image relationship for successful embedded binding and verify
    its target exists. Missing targets retain the picture's identity and an
    unsupported child plus DRAWING_IMAGE_MISSING.

### `href`

- **Output**
  - img/@href; external image resource descriptor.
- **OOXML**
  - a:blip/@r:link to an external image relationship.
- **Parsing**
  - Preserve the saved URI. Never download it or treat the URI as a package
    part. Resource reads remain bounded to available original package bytes.

### `link`

- **Output**
  - img/@link.
- **OOXML**
  - That picture's cNvPr/a:hlinkClick/@r:id.
- **Parsing**
  - Retain an explicitly saved click target independently of the image source.
