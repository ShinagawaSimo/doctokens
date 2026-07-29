# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A DOCX-to-semantic-HTML5 parser that converts `.docx` files into LLM-readable HTML5 markup (with implicit close tags for token efficiency). Pure Python 3, zero external dependencies — relies entirely on stdlib.

## Commands

```bash
# Parse a single .docx
python docx_parser_cli.py <file.docx>                          # output to out/<stem>/parsed.html
python docx_parser_cli.py <file.docx> --out custom_out_dir     # custom output base
python docx_parser_cli.py <file.docx> --revision-mode review   # show insertions/deletions
python docx_parser_cli.py <file.docx> --no-runs                # strip inline XML, keep merged text only

# Run tests
python -m pytest tests/ -v
# or
python -m unittest discover -s tests -v
```

## Architecture

```
docx_llm_parser/
  __init__.py          # Public API: DocxParser, ParseOptions, ParsedDocument, parse_many, BatchParseResult
  parser.py            # Orchestration: reads package → styles → numbering → assets → embedded objects → body → ancillary → debug/metrics
  concurrency.py       # parse_many() — ThreadPoolExecutor per-document concurrency
  core/
    models.py          # ParseOptions, ParsedDocument, ParseWarning, StyleRecord, RelationshipRecord
    constants.py       # OOXML namespace map (NS) + XML helper functions (qn, attr, first_child, child_elements, is_on, local_name)
    package.py         # PackageReader — ZIP entry validation, Content_Types.xml, .rels discovery with path traversal safety
    relationships.py   # RelationshipIndex — frozen multi-index (by source+id, by source, by type) built once from all .rels
    debug.py           # DebugWriter — writes intermediate JSON/JSONL to <output_dir>/debug/
    metrics.py         # MetricsRecorder — per-stage timing with context manager, counter snapshots
  ooxml/
    styles.py          # StylesParser → StyleMap with cached heading-level/numbering/run-format inheritance resolution
    numbering.py       # NumberingParser → NumberingMap (immutable definitions) + NumberingState (per-document mutable counters)
    formatting.py      # Run format extraction (bold/italic/underline/strike/color/highlight/bg) with merge and visible-filter
  extractors/
    body.py            # DocumentBodyParser — iterparse word/document.xml, produces ordered paragraph/heading/table blocks
    inline.py          # InlineParser — shared across body + ancillary; parses runs, hyperlinks, drawing/pict, equations, fields, notes, comments
    assets.py          # AssetExtractor — exports embedded images to assets/, builds (sourcePart, rId) → asset lookup
    objects.py         # EmbeddedObjectExtractor — chart XML and SmartArt data model lightweight parsing
    ancillary.py       # AncillaryParser — headers, footers, footnotes, endnotes, comments
  renderers/
    html5.py           # Final LLM HTML5 output: implicit close + short attrs (~31% token savings)
    _text_utils.py     # Shared run merging & format filtering (used by all renderers)
    _metrics.py        # Shared render metrics recording
```

### Parse Pipeline (DocxParser.parse)

```
PackageReader (validate ZIP, build entry index, read Content_Types + all .rels)
  → StylesParser → StyleMap (with caches)
  → NumberingParser → NumberingMap
  → AssetExtractor (exports images, builds lookup)
  → EmbeddedObjectExtractor (chart/SmartArt lightweight data)
  → DocumentBodyParser (iterparse body, uses InlineParser + NumberingState)
  → AncillaryParser (headers/footers/footnotes/endnotes/comments, reuses InlineParser)
  → DebugWriter (dump all intermediate state as JSON)
  → MetricsRecorder snapshots
```

The final HTML5 markup (`parsed.html`) is written by `renderers/html5.py:write_outputs()` using streaming `iter_html5()` to handle large documents without holding the full HTML string in memory. HTML5 implicit close rules eliminate block-level closing tags, saving ~31% tokens vs XML.

### Key Design Decisions

- **No dependency on `python-docx`**. All OOXML parsing is direct via `xml.etree.ElementTree.iterparse` for the body (streaming) and `ET.parse` for smaller parts.
- **Single-document concurrency only**. `parse_many()` parallelizes at the document level via `ThreadPoolExecutor`; parsing within a single document is sequential.
- **Style inheritance is cached**. `StyleMap` resolves heading level, numbering, and run format through `basedOn` chains once, then caches. Hot paths (every paragraph/run) only do dict lookups.
- **Numbering state is mutable per-document**. `NumberingState` tracks counter advancement per `numId`/`ilvl` — a fresh instance is created for each document parse.
- **Debug is always on** during MVP development. No `--no-debug` flag. All intermediate state goes to `<output_dir>/debug/`.
- **The parser is the authority**. Headings are detected ONLY from `w:outlineLvl` in styles (or inherited via `basedOn`), never from paragraph text heuristics or font size.

### Trust Boundary (from dev guide)

Validate at system boundaries only:
- ZIP entry count/size limits, path traversal checks (`PackageReader._validate_entry_name`)
- Optional parts missing (`styles.xml`, `numbering.xml`, `footnotes.xml`) — produce empty containers
- External resources (images with `TargetMode=External`) — record URL only, never fetch
- Debug write failures — append `ParseWarning`, don't abort
- Unsupported OOXML nodes — append `ParseWarning` with code

Do NOT add defensive defaults for internal fields like `block["type"]`, `block["page"]`, `table["rows"]` — broken internal state should surface early, not be silently swallowed.

## Output Structure

```
out/<docx_stem>/
  parsed.html         # Final LLM-readable HTML5 semantic markup
  assets/             # Exported embedded images (img1.png, img2.jpg, ...)
  debug/
    zip_index.json
    content_types.json
    relationships.json
    styles.json
    numbering.json
    internal_blocks.json
    assets.json
    embedded_objects.json    # charts + smartarts
    ancillary.json           # headers/footers/footnotes/endnotes/comments
    body_events.jsonl
    warnings.json
    summary.json
    metrics.json             # per-stage timing + output size counters
```

## Research Documents

- `word-docx-parsing-research.md` — Initial research on OOXML structure and parsing approaches
- `word-document-nonfunctional-optimization-research.md` — Non-functional optimization research (performance, memory, concurrency)
- `word-docx-parser-mvp-dev-guide.md` — The canonical dev guide (v0.6, 2026-07-28): defines scope, trust boundary, output format, and architecture decisions. **Authoritative for design intent.**
