# Relationships

[COMMON](README.md) / Relationships

Relationship identity is scoped to its source part.

## Processing

Read direct `rel:Relationship` children of the relationship part in source order. Other child elements are ignored. An absent relationship part yields an empty sequence; malformed XML propagates an XML parse error to the format parser.

## Fields

### `source_part`

- **Output**
  - Resource and diagnostic context.

- **OOXML**
  - `<parent>/_rels/<name>.rels`; package relationships use `_rels/.rels`.

- **IR**
  - `RelationshipRecord.source_part: str`

- **Parsing**
  - Retain the supplied owner string; package-root ownership is `""`. To form the relationship-part path, replace backslashes with `/`, remove leading `/`, and insert `_rels/` before the basename and `.rels` after it.

### `id`

- **Output**
  - Internal lookup key.

- **OOXML**
  - `rel:Relationship/@Id`

- **IR**
  - `RelationshipRecord.id: str`

- **Parsing**
  - Read `rel.attrib["Id"]`. Index by `(source_part, id)`; the last duplicate replaces earlier entries in single-record lookup. Ordered source/type queries retain all records, including duplicates.

- **Diagnostics**
  - Missing attribute: `KeyError` at package reading. An empty string is retained.

### `type`

- **Output**
  - Selects image, hyperlink, chart, slide, worksheet, and other handlers.

- **OOXML**
  - `rel:Relationship/@Type`

- **IR**
  - `RelationshipRecord.type: str`

- **Parsing**
  - Read `rel.attrib["Type"]`; match handler URIs by exact string.

- **Diagnostics**
  - Missing attribute: `KeyError` at package reading. An empty string is retained.

### `target`

- **Output**
  - Raw source target.

- **OOXML**
  - `rel:Relationship/@Target`

- **IR**
  - `RelationshipRecord.target: str`

- **Parsing**
  - Read `rel.attrib["Target"]`; retain the string before normalization.

- **Diagnostics**
  - Missing attribute: `KeyError` at package reading. An empty string is retained.

### `target_mode`

- **Output**
  - External target classification.

- **OOXML**
  - `rel:Relationship/@TargetMode`

- **IR**
  - `RelationshipRecord.target_mode: str | None`

- **Parsing**
  - Only the exact string `"External"` selects external resolution. Other values use internal resolution. Parsing does not fetch external targets.

- **Absence and defaults**
  - Missing: `None`.

### `resolved_target`

- **Output**
  - Input to part lookup or public link/resource target.

- **OOXML**
  - Source part + `@Target` + `@TargetMode`.

- **IR**
  - `RelationshipRecord.resolved_target: str | None`

- **Parsing**
  - `target_mode == "External"`: return the original target.
  - Otherwise replace backslashes with `/`. A target beginning with `/` becomes `posixpath.normpath(target.lstrip("/"))`.
  - Other targets become `posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))`.
  - This step does not percent-decode, remove URI fragments, check existence, or reject a result beginning with `..`. Subsequent part access and format-specific handlers determine the result of lookup.


## Source references

- [RelationshipRecord](../../packages/ooxml_llm_core/src/ooxml_llm_core/models.py#L31)
- [RelationshipIndex](../../packages/ooxml_llm_core/src/ooxml_llm_core/relationships.py#L25)
- [PackageReader](../../packages/ooxml_llm_core/src/ooxml_llm_core/package.py#L31)
- [PackageReader.read_relationships_for_part](../../packages/ooxml_llm_core/src/ooxml_llm_core/package.py#L172)
- [rels_path_for_part](../../packages/ooxml_llm_core/src/ooxml_llm_core/package.py#L256)
- [resolve_relationship_target](../../packages/ooxml_llm_core/src/ooxml_llm_core/package.py#L279)
