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

### Projection boundaries independent of extraction history

The following families have explicit renderer permissions. A semantic session
can retain every source value in a row while a lower-density render still emits
only that density's permitted fields. These rules apply to direct source
declarations and inherited/resolved values alike. Atomic format specifications
remain the definitions of each field, rather than a generic filter by field name.

| Field family | Plain | Structural | Semantic |
| --- | --- | --- | --- |
| DOCX/PPTX/XLSX comment text and review status | Text and status | Text and status | Text and status |
| Comment author/date, valid reply parent and supported target | Omitted | Retained when known | Retained when known |
| Comment rich emphasis/citation/mention semantics | Readable text | Readable structure | Supported inline semantics |
| DOCX control current content and human label | Marker/content/label | Wrapper/content/label | Content and semantic control projection |
| DOCX control type, choices and content/control lock | Omitted | Omitted | Retained under the control contract |
| DOCX revisions/property changes, ruby annotation and emphasis/color | Selected text/base text | Selected text/base structure | Supported revision/ruby/format semantics |
| DOCX paragraph formatting properties and table-cell background | Omitted | Omitted | Retained reading properties |
| PPTX inherited placeholder role, paragraph level and explicit links | Readable text/indent | Retained structure/links | Retained structure/links |
| PPTX run/table emphasis and color | Omitted | Omitted | Retained reading semantics |
| PPTX nonmatching shape name | Omitted | Omitted | Retained under the English default-name heuristic |
| PPTX/XLSX group names and explicit containment | Omitted | Retained, with English default names filtered | Same |
| XLSX conditional-format conditions, priority and stop behavior | Compact unsupported marker only when unreadable | Retained | Retained |
| XLSX conditional-format dxfStyle and formatDetails | Omitted | Omitted | rule/@style and visual details |
| XLSX validation constraints and effective error enforcement | No readable rule expansion | Retained | Retained |
| XLSX validation saved input/error messages | Omitted | Omitted | Retained |
| XLSX resolved color-filter condition | Compact filter marker | Retained predicate color | Retained predicate color |
| XLSX cell/run font/fill, style-range and number-format color metadata | Omitted | Omitted | Retained reading styles |
| XLSX enabled sheet protection and affirmative applicable cell restrictions | Omitted | Omitted | sheet-protection; locked=true and formula-hidden=true when applicable |
| XLSX formatted display value | Retained | Retained | Retained |
| Chart/SmartArt reading previews | Bounded plain summary | Shared bounded structure | Shared bounded structure |
| Raw hints, control binding provenance and bare dxf lookup indices | Not body fields | Not body fields | Not body fields |

In particular, a color used as a filter predicate is not the same permission as
a decorative font/fill color. Likewise validation errorStyle describes effective
enforcement, whereas conditional-format dxfStyle describes appearance. Do not
remove one merely because its source field name resembles the other.

DOCX comment threading/status extraction belongs to every public reading plan.
A comment with saved resolved state must not become unknown merely because a
one-shot lower-density read omitted the threading pass. Legacy or unreadable
state remains unknown in both one-shot and session projections.

XLSX standard dxf references and inline x14 dxf can both populate semantic IR.
The conditional-format renderer permits style/details only at semantic density,
even after a prior semantic render populated formatting caches. Low-density
renders never mutate or discard richer data needed by later semantic reads.
Output iteration uses the same current-density projection as a complete read.

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
