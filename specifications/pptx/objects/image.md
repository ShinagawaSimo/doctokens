# Pictures

[PPTX](../README.md) / Pictures

Pictures resolve the first descendant blip against the asset index.

## Fields

### `assetId`

- **Output**
  - `img/@id`; fallback shape ID.

- **OOXML**
  - a:blip/@r:embed, fallback @r:link.

- **IR**
  - `ShapeBlock.assetId: str`

- **Parsing**
  - Lookup `(slide-part,rId)`. Missing blip skips picture; missing rId/asset retains placeholder.

- **Diagnostics**
  - PICTURE_MISSING_BLIP, PICTURE_MISSING_RID, PICTURE_ASSET_MISSING.

### `alt`

- **Output**
  - `img/@alt`; plain `[Image: alt]`.

- **OOXML**
  - cNvPr/@descr, fallback @title.

- **IR**
  - `ShapeBlock.alt: str`

- **Parsing**
  - Copy nonempty source string in both XML densities.

### `href`

- **Output**
  - Resource target; no current img/@href.

- **OOXML**
  - External asset href.

- **IR**
  - `ShapeBlock.href: str`

- **Parsing**
  - Copy only for external assets; no download.


## Source references

- [SlideParser._picture_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L467)
- [_append_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L54)
