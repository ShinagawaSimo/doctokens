# Density

[COMMON](README.md) / Density

Density selects a format-specific extraction plan and output projection.
The renderer enforces the current density's element/field permission set.
Retaining richer session IR does not authorize extra fields at a lower density;
extraction plans optimize cost rather than establish a different output schema.
Existing format-specific navigation/resource identity contracts remain distinct.

Public reading output prioritizes information needed to answer document tasks:
content, hierarchy, meaningful emphasis, source coordinates, resource lookup and
explicit relationships. It is not an exhaustive source or visual projection.
Redundant attributes, implicit defaults and decoder provenance are omitted when
they do not add reading information. Exact source/layout projection belongs to
the future, non-public `full` density; no `full` API is introduced here.

## Processing

| Feature | DOCX plain / structural | DOCX semantic / session |
| --- | --- | --- |
| Body, image index, notes, comments, saved chart/diagram data | Yes | Yes |
| Comment threading and saved review status | Yes | Yes |
| Run formatting, headers/footers | No | Yes |
| Explicit optional OCR on retained reading images | Read time | Read time |
| Raw hints | No | Session only, subject to options |

| Feature | PPTX plain / structural | PPTX semantic / session |
| --- | --- | --- |
| Slide index, text, images, notes, comments, navigation, objects | Yes | Yes |
| Inherited list defaults and placeholder roles | Yes | Yes |
| Character formatting, theme colors | No | Yes |
| Explicit optional OCR on retained reading images | Read time | Read time |
| Geometry sorting and background extraction | No | No |

| Feature | XLSX plain | XLSX structural | XLSX semantic / session |
| --- | --- | --- | --- |
| Values, comments, rules, tables, drawings, pivots, rich values, controls | Yes | Yes | Yes |
| Formula text, hyperlinks, names, external links, style indices | No | Yes | Yes |
| Rich text and semantic styles | No | No | Yes |

XLSX number-format display processing is available in every density. Resource identifiers and diagnostics are plan-dependent; comparisons across plans must use the source owner and reference, not assume identical resource numbering.

The tables describe extraction availability, not permission to emit every IR
field. Atomic format specifications define the public density projection. OCR
is explicitly derived text in all three reading densities, with the same status
policy. It runs only for images actually retained in the requested body/window;
content intentionally omitted at that density does not trigger recognition.
Opening a session, reading its directory or reading binary image bytes does not
initiate OCR. Results belong to the explicit session and are reused by image
source part; independent responses still expand text at every image position.

Across formats, plain comments retain text and review status. Structural adds
known authors, dates, reply links, IDs and supported targets; semantic retains
additional useful inline semantics or mentioned people. Status is
active/resolved/closed/unknown; absence of readable source state is not active.

## Fields

### `density`

- **Output**
  - `plain`: `doctokens-plain/1.0`, `text/plain`.
  - `structural`, `semantic`: `doctokens-xml/1.0`, `application/xml`.

- **Source**
  - Call argument; no OOXML attribute.

- **IR**
  - `Literal["plain", "structural", "semantic"]`

- **Parsing**
  - DOCX/PPTX default: `semantic`. XLSX default: `structural`.
  - One-shot plans omit unused work; sessions retain semantic-level data for subsequent projections.

- **Diagnostics**
  - Other values: `ValueError`.
