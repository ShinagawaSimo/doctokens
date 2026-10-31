# Images

[DOCX](../README.md) / Images

Image records are indexed by owning part and relationship ID.

## Fields

### `id`

- **Output**
  - Inline and asset-list `img/@id` in both structural and semantic densities.

- **OOXML**
  - Image relationship; DrawingML `a:blip/@r:embed` or VML `v:imagedata/@r:id`.

- **IR**
  - `ImageAsset.id`; `InlineObject.assetId: str`

- **Parsing**
  - Allocate img1, img2, ... for accepted assets. Resolve inline source by `(part,rId)` using the owning XML part's relationships.
  - VML reads each `v:imagedata/@r:id` in source order, including those within groups, and uses the same image binding as DrawingML. Each occurrence refers to the existing resource; repeated appearances do not allocate new ids.
  - Both XML densities preserve the bound id in body, table and retained ancillary content, including page-window reads. No id is synthesized for an unresolved image.
  - DrawingML does not use `r:link`. VML does not infer a package relationship from `src` or `o:relid`.

- **Absence and defaults**
  - Unresolved inline image becomes a drawing placeholder.

- **Diagnostics**
  - Missing embedded target: `IMAGE_TARGET_MISSING`, source-part locator.

### `source`

- **Output**
  - Resource descriptor source.

- **OOXML**
  - Relationship @TargetMode.

- **IR**
  - `ImageAsset.source: "external" | "embedded"`

- **Parsing**
  - Exact External → external; otherwise require an existing package part.

### `href`

- **Output**
  - Semantic asset-list `img/@href`; no inline href.

- **OOXML**
  - External relationship @Target.

- **IR**
  - `ImageAsset.href: str`

- **Parsing**
  - Copy external target without downloading.

### `zipPath`

- **Output**
  - Binary resource locator.

- **OOXML**
  - Resolved internal relationship target.

- **IR**
  - `ImageAsset.zipPath: str`

- **Parsing**
  - Use canonical package path; read bytes only through read_resource or supplied OCR.

### `contentType`

- **Output**
  - Resource descriptor content_type.

- **OOXML**
  - [Content_Types].xml.

- **IR**
  - `ImageAsset.contentType: str`

- **Parsing**
  - Override by part, then extension default, then mimetypes.guess_type; omit if unresolved.

### `file`

- **Output**
  - No current output.

- **OOXML**
  - No package extraction path.

- **IR**
  - Optional `ImageAsset.file: str`

- **Parsing**
  - Not populated by AssetExtractor; binary resources remain in the package.

### `alt`

- **Output**
  - Inline `img/@alt` in structural and semantic; readable plain image description.

- **OOXML**
  - DrawingML docPr/@descr, then @title; VML owning shape @alt, @title and imagedata/@o:title.

- **IR**
  - `InlineObject.alt: str`, with optional `InlineObject.title` fallback.

- **Parsing**
  - DrawingML uses [drawing metadata](drawing.md).
  - VML uses its owning shape's nonempty alt, then title. A nonempty `imagedata/@o:title` supplies title when the shape has none.
  - Both XML densities use alt or title, omitting the attribute when neither has non-whitespace content. Preserve the original spacing of a readable description. Plain uses the same description and otherwise emits [Image]. Do not fabricate alt from drawing names, shape IDs or filenames.
  - The same projection applies to images in body paragraphs, retained table cells, text-box stories and retained ancillary content, including page windows. Sibling shapes do not share description fields.
