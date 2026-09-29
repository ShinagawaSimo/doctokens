# Media

[PPTX](../README.md) / Media

Media placeholders do not decode audio or video.

## Fields

### `kind`

- **Output**
  - `media/@kind`; plain [Video]/[Audio]/[Media].

- **OOXML**
  - First descendant videoFile/audioFile.

- **IR**
  - `ShapeBlock.kind: str`

- **Parsing**
  - First recognized descendant chooses video/audio; default media.

### `assetId`

- **Output**
  - `media/@id`; fallback shape ID.

- **OOXML**
  - Media element @r:embed.

- **IR**
  - `ShapeBlock.assetId: str`

- **Parsing**
  - Resolve asset index; preserve placeholder if absent.

- **Diagnostics**
  - MEDIA_MISSING_RID, MEDIA_ASSET_MISSING.

### `href`

- **Output**
  - Resource external target only.

- **OOXML**
  - Resolved external media relationship.

- **IR**
  - `ShapeBlock.href: str`

- **Parsing**
  - Copy target string; no playback.


## Source references

- [SlideObjectParser._media_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/objects.py#L73)
