# Pictures

[PPTX](../README.md) / Pictures

Pictures resolve the first descendant blip against the asset index.
Missing blip/relationship/resource retains the known image occurrence and its
readable description. The XML image contains an unsupported image child; plain
uses `[Image unavailable: description]` or `[Image unavailable]`.

OLE graphic frames retain their saved `p:oleObj/p:pic` preview, using a direct
representation or `mc:Fallback` for the OLE/VML compatibility form. Preview
images add `kind="ole-preview"` and `progid` from `progId`, falling back to the
object name or OLE. If no picture is saved, retain a descriptive embedded shape.
Emit `OLE_OBJECT_NOT_PARSED` because the embedded program/legacy equation itself
is not decoded or executed. A preview is not reconstructed equation text.

## Fields

### `assetId`

- **Output**
  - `img/@id` for a known image asset. Missing bindings omit it; shape-id still
    identifies the occurrence and is not advertised as a binary resource key.

- **OOXML**
  - a:blip/@r:embed, fallback @r:link.

- **IR**
  - `ShapeBlock.assetId: str`

- **Parsing**
  - Lookup `(slide-part,rId)`. Missing blip/rId/asset retains an unreadable image
    occurrence, preserving existing alt and navigation. No resource ID is guessed.

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
  - Prefer a non-whitespace descr, then a non-whitespace title; preserve source
    spacing in a readable description. Omit absent/blank descriptions. Do not
    use automatic names, shape IDs or filenames as descriptions.
  - OLE previews retain an explicit readable object-frame description when
    present; otherwise use the preview picture's description/title, then the
    frame title. Blank object metadata never erases a readable preview caption.
    Picture titles are consumed as fallback rather than retained as unused data.
  - Plain OLE previews include readable text, for example
    `[OLE preview: Worksheet preview]`; an unavailable preview retains both
    its image role and description. Generic unsupported shapes also retain an
    independently readable description without claiming a binary image binding.

### `href`

- **Output**
  - Resource target; no current img/@href.

- **OOXML**
  - External asset href.

- **IR**
  - `ShapeBlock.href: str`

- **Parsing**
  - Copy only for external assets; no download.
