# Media

[PPTX](../README.md) / Media

Media placeholders do not decode audio or video.

## Saved representations

Recognize the standard Office 2006 audio/video relationship types, the legacy
Office 2006 media type and Office 2007 media relationships. Embedded targets must
exist in the package. External targets are indexed without download or playback.
Media relationships sharing an embedded part or exact external target share one
resource id; image resource ids keep their existing relationship-based allocation.

For a media-bearing `p:pic`, retain the original `img` and its OCR, then append a
`media` node with `poster` referring to the image resource id when available.
The extra media node is part of that source shape, not a second visible shape.
Plain output retains the image placeholder followed by [Video]/[Audio]/[Media].
If no poster is saved, retain the media object alone. If the media relationship
is unresolved, retain its declaration without inventing a resource id.

## Fields

### `kind`

- **Output**
  - `media/@kind`; plain [Video]/[Audio]/[Media].

- **OOXML**
  - `a:videoFile`, `a:audioFile`, `a:wavAudioFile` and `p14:media` declarations.

- **IR**
  - `ShapeBlock.kind: str`

- **Parsing**
  - Video declaration selects video, otherwise audio declaration selects audio.
  - A generic media declaration can use the resolved content type; otherwise media.
  - Legacy standalone producer representations using `p:videoFile`/`p:audioFile` remain accepted.

### `assetId`

- **Output**
  - `media/@id`; fallback shape ID.

- **OOXML**
  - `p14:media/@r:embed` or `@r:link`; audio/video file `@r:link` or `@r:embed`.

- **IR**
  - `ShapeBlock.assetId: str`

- **Parsing**
  - Resolve by owning part and relationship id, requiring a media asset.
  - Prefer a resolvable p14 target, then saved legacy file references in source order.
  - Standalone objects retain their existing shape-id placeholder if unresolved;
    companion media declarations without a resolved id omit `id`.

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

### `poster`

- **Output**
  - Companion `media/@poster` in both XML densities.
- **IR**
  - `ShapeBlock.mediaId` and `ShapeBlock.mediaKind` attach media to the retained picture;
    its existing `assetId` supplies the poster id.
- **Absence**
  - Omit when the poster image cannot be bound. Missing media must not erase the poster.

### `owner-shape`

- **Output**
  - Companion `media/@owner-shape` in both XML densities.
- **Parsing**
  - References the retained poster element's slide-local `shape-id`. The poster
    and companion media describe one saved picture shape. Standalone media
    carries its own `shape-id` instead.
