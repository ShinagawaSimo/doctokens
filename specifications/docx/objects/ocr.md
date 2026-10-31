# Image OCR association

[DOCX](../README.md) / Image OCR association

An explicitly supplied adapter recognizes only images retained by the requested
body/page window and density. Parsing or opening a session does not run OCR.
Read-time results use the [common OCR contract](../../common/ocr.md).

## Fields

### `id`

- **Output**
  - Both XML densities: sibling `<ocr-text id="img1">...</ocr-text>` after each
    corresponding body image. Plain places a marked OCR block after the image.
- **Source**
  - The retained image resource's asset ID and embedded source part.
- **IR**
  - `ParsedDocument.ocr_results[asset_id]`, containing score-free reading records.
- **Reading**
  - Reuse the source-part result within the explicit session; repeat text at
    every image occurrence and make independent reads self-contained. No OCR
    text is repeated in the asset directory. Binary/resource-directory reads
    and native-text search do not initiate recognition.

### `text`

- **Output**
  - XML character data or a plain `[OCR]`...`[/OCR]` block in all three densities.
- **Source**
  - Successful normalized adapter text.
- **Reading**
  - Preserve full text and internal line breaks; do not replace it by a plain
    excerpt. Keep it distinct from native document text. Retained table and
    textbox images participate; images beyond the current table preview do not.
  - Plain omits headers/footers and unreferenced notes under its existing
    reading policy. Such omitted content does not trigger OCR. Page selection
    occurs before recognition; unrelated image parts are not read for OCR.

### `low_confidence`

- **Output**
  - XML @low-confidence=true or plain `[OCR low-confidence]`.
- **Source**
  - The common character-weighted normalized score below 0.8.
- **Reading**
  - Show the hint with complete recognized text. Do not expose the numeric
    score. Missing confidence data produces no invented assessment.

### `status`

- **Output**
  - Empty recognition emits no OCR node/marker. Failure emits
    `<ocr-text id="img1" error="true"/>` or plain `[OCR failed]`.
- **Diagnostics**
  - New failed source-part attempts append OCR_FAILED with diagnostic details.
    Session report snapshots include read-time outcomes; repeated body images
    do not duplicate a cached attempt's warning.
