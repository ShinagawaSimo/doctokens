# Saved EMF text

[COMMON](README.md) / Saved EMF text

Explicit image-text resources read saved native text without drawing rendering,
OCR or OLE execution. Original image bytes remain independently available.

## Fields

### `source`

- **Output**
  - image-text/@source identifies the original image resource inside a complete
    format-specific semantic DTX resource document.
- **Source**
  - `session.render_resource("image-text", image_id)` in DOCX/PPTX/XLSX.
- **Parsing**
  - Require a known embedded image. Missing ID raises KeyError; external
    sources are never downloaded. Default bodies/search/OCR remain unchanged.

### `text`

- **Output**
  - One text child per readable native text operation, in record order.
- **Source**
  - EMR_EXTTEXTOUTW/A and EMR_POLYTEXTOUTW/A.
- **Parsing**
  - Check record-relative string offsets and counts. Decode UTF-16LE directly;
    ANSI requires an explicit supported selected-font charset/codepage.
    Host-dependent default/ANSI/OEM encodings are not guessed.
  - Preserve saved text and record boundaries. No coordinate-based joining,
    deduplication, glyph-index guessing or business-edge inference is performed.

### `partial`

- **Output**
  - image-text/@partial=true with limitation/@code when incomplete.
- **Source**
  - Unsupported text operations, glyph indices, unresolved encoding, malformed
    header/records/EOF, EMF+ content or budget exhaustion.
- **Parsing**
  - Preserve independently readable text. A known unreadable text operation
    has an unsupported marker at its position. An unsupported image format
    yields a marked result, not an apparently empty decoded EMF.
  - Companion EMF text may be readable while EMF+ content remains partial.
    This operation does not claim visual/editable recovery.

### `limits`

- **Output**
  - record-limit/character-limit limitations; no invented continuation.
- **Parsing**
  - At most 100000 records including the header. The 16000-character serialized
    output budget includes escaping/markup and reserved envelope/limitation
    space. Stop clearly on exhaustion. Existing package byte limits apply.
  - Invalid record offsets cannot address outside their record. XML-invalid
    characters and decoding failures are reported. No global cache is added.
