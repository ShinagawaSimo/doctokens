# Binary asset records

[PPTX](../README.md) / Binary asset records

Images and media are indexed separately without eager binary extraction.

## Fields

### `id`

- **Output**
  - Resource ID.

- **OOXML**
  - Relationship traversal grouped image then media.

- **IR**
  - `ImageAsset.id: str`

- **Parsing**
  - img1... / media1...; increment before validation, so missing parts leave gaps.

### `type`

- **Output**
  - Resource kind.

- **OOXML**
  - Relationship type image/media.

- **IR**
  - `str`

- **Parsing**
  - image or media.

### `source`

- **Output**
  - Resource source.

- **OOXML**
  - Relationship TargetMode.

- **IR**
  - `str`

- **Parsing**
  - External → external; otherwise embedded.

### `href`

- **Output**
  - External resource target.

- **OOXML**
  - Relationship Target.

- **IR**
  - `str`

- **Parsing**
  - Copy for external source.

### `zipPath`

- **Output**
  - Binary package location.

- **OOXML**
  - Resolved internal target.

- **IR**
  - `str`

- **Parsing**
  - Require existing part.

- **Diagnostics**
  - ASSET_PART_MISSING, source-part locator.

### `contentType`

- **Output**
  - Resource MIME type.

- **OOXML**
  - Content Types/extension.

- **IR**
  - `str`

- **Parsing**
  - Part override, extension default, mimetypes guess, then application/octet-stream.

### `file`

- **Output**
  - No output.

- **OOXML**
  - No extraction file.

- **IR**
  - Optional str.

- **Parsing**
  - Not populated by current extractor.


## Source references

- [AssetExtractor](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/resources/assets.py#L22)
