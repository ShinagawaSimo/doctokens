# Images

[DOCX](../README.md) / Images

Image records are indexed by owning part and relationship ID.

## Fields

### `id`

- **Output**
  - Semantic inline `img/@id`; asset-list `img/@id` in both XML densities.

- **OOXML**
  - Image relationship; drawing `a:blip/@r:embed`.

- **IR**
  - `ImageAsset.id`; `InlineObject.assetId: str`

- **Parsing**
  - Allocate img1, img2, ... for accepted assets. Resolve inline source by `(part,rId)`. The drawing scanner does not use r:link.

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
  - Semantic inline `img/@alt`.

- **OOXML**
  - Drawing docPr/@descr.

- **IR**
  - `InlineObject.alt: str`

- **Parsing**
  - Use [drawing metadata](drawing.md); structural inline images omit alt and id.


## Source references

- [AssetExtractor.extract](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/assets.py#L30)
- [_append_image_or_placeholder](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/objects.py#L166)
- [_append_inline_object](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L167)
- [_append_assets](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L297)
