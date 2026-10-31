# Image OCR association

[PPTX](../README.md) / Image OCR association

An explicitly supplied adapter recognizes images at body-read time in all three
densities. Parsing/opening a session does not run OCR. The current slide window
and density's retained image scope determine recognition work; see the
[common OCR contract](../../common/ocr.md).

## Fields

### `id`

- **Output**
  - Both XML densities: sibling ocr-text/@id after every corresponding picture.
    Plain emits a marked OCR block after its image marker.
- **Source**
  - Picture assetId. Existing retained semantic background IR can associate an
    embedded background asset; omitted backgrounds do not trigger OCR.
- **IR**
  - `ParsedPresentation.ocr_results` contains score-free records by asset ID.
- **Reading**
  - Reuse a recognized embedded source part within the explicit session; every
    picture occurrence still expands the complete text. Independent responses
    are self-contained. Direct binary reads, directories and native-text search
    do not initiate recognition. External images are not downloaded.

### `text`

- **Output**
  - Complete XML OCR character data or a plain `[OCR]`...`[/OCR]` block.
- **Source**
  - Successful normalized adapter text.
- **Reading**
  - Preserve full text/line breaks, including on repeated pictures and media
    posters. Select slides before recognition; unrelated parts are not OCRed.

### `low_confidence`

- **Output**
  - XML @low-confidence=true or plain `[OCR low-confidence]`.
- **Source**
  - The common non-whitespace-character-weighted score strictly below 0.8.
- **Reading**
  - Emit the warning with complete text and no numeric score. Without usable
    engine recognition scores, do not invent confidence.

### `status`

- **Output**
  - Successful empty results add no OCR marker. Errors add
    `<ocr-text id="img1" error="true"/>` or plain `[OCR failed]`.
- **Diagnostics**
  - OCR_FAILED details are kept outside document text. Session reports reflect
    fresh read-time failures without repeating warnings for cached attempts.
