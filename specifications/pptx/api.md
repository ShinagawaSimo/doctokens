# Parsing and selection

[PPTX](README.md) / Parsing and selection

parse_pptx/open_pptx accept paths or complete ZIP bytes.

## Processing

```python
def _select_slides(
    presentation: ParsedPresentation,
    slide: int | None,
    span: int,
) -> tuple[ParsedPresentation, dict[str, object]]:
    if slide is not None and (isinstance(slide, bool) or not isinstance(slide, int) or slide == 0 or slide < -1):
        raise ValueError("slide must be -1 or a positive integer")
    if isinstance(span, bool) or not isinstance(span, int) or span <= 0:
        raise ValueError("span must be a positive integer")
    if slide is None:
        if span != 1:
            raise ValueError("span requires slide")
        return presentation, {"kind": "all"}

    start = len(presentation.slides) + slide if slide < 0 else slide - 1
    if start < 0 or start >= len(presentation.slides):
        return dataclasses.replace(presentation, slides=[], comments=[]), {
            "kind": "slide",
            "start": slide,
            "span": span,
            "empty": True,
        }
    selected = presentation.slides[start : start + span]
    selected_ids = {item["id"] for item in selected}
    comments = [item for item in presentation.comments if item.get("slideId") in selected_ids]
    return dataclasses.replace(presentation, slides=selected, comments=comments), {
        "kind": "slide",
        "start": start + 1,
        "span": span,
    }
```

## Fields

### `source`

- **Output**
  - PPTX input.

- **Source**
  - OPC package.

- **IR**
  - `str | Path | bytes`

- **Parsing**
  - Passed to PackageReader.

### `density`

- **Output**
  - DTP/DTX selection.

- **Source**
  - Call option.

- **IR**
  - `plain | structural | semantic`

- **Parsing**
  - Default semantic. Structural/plain one-shot skips theme/layout formatting; session retains these for later rendering.

### `slide`

- **Output**
  - Starting accepted-slide number.

- **Source**
  - Call option.

- **IR**
  - `int | None`

- **Parsing**
  - None → all; positive int → start. See the selection algorithm above.

### `span`

- **Output**
  - Maximum slides in selection.

- **Source**
  - Call option.

- **IR**
  - `int = 1`

- **Parsing**
  - Positive int; see the selection algorithm above. Result resource directory describes the full parsed presentation.

### `ocr`

- **Output**
  - OCR adapter.

- **Source**
  - ParseOptions.

- **IR**
  - `object | None = None`

- **Parsing**
  - Common OCR protocol.

### `ocr_workers`

- **Output**
  - OCR concurrency.

- **Source**
  - ParseOptions.

- **IR**
  - `int = 4`

- **Parsing**
  - Common OCR validation.

### `ocr_timeout`

- **Output**
  - OCR seconds.

- **Source**
  - ParseOptions.

- **IR**
  - `float = 120.0`

- **Parsing**
  - Common OCR validation.


## Source references

- [parse_pptx](../../packages/pptx_llm_parser/src/pptx_llm_parser/api.py#L271)
- [PptxReadSession](../../packages/pptx_llm_parser/src/pptx_llm_parser/api.py#L126)
