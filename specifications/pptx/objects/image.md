# Pictures

[PPTX](../README.md) / Pictures

Pictures resolve the first descendant blip against the asset index.

OLE graphic frames retain their saved `p:oleObj/p:pic` preview, using a direct
representation or `mc:Fallback` for the OLE/VML compatibility form. Preview
images add `kind="ole-preview"` and `progid` from `progId`, falling back to the
object name or OLE. If no picture is saved, retain a descriptive embedded shape.
Emit `OLE_OBJECT_NOT_PARSED` because the embedded program/legacy equation itself
is not decoded or executed. A preview is not reconstructed equation text.

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
