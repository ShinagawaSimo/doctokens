"""Publish the same cross-field and host-budget rules used by tool execution."""

from __future__ import annotations

from typing import Any

from .config import RuntimeConfig
from .schemas import Arguments, BaseSourceArgs, QueryArgs, ResultArgs, XlsxReadArgs


def result_limits(config: RuntimeConfig) -> dict[str, int | str]:
    maximum = config.max_chunk_size
    return {
        "requested_length_max": maximum,
        "default_length": min(config.result_chunk_chars, maximum),
        "effective_text_chars": min(maximum, config.reply_chars),
        "effective_binary_bytes": min(maximum, config.reply_chars // 4 * 3),
        "text_unit": "characters",
        "binary_unit": "bytes",
    }


def input_schema(model: type[Arguments], config: RuntimeConfig) -> dict[str, Any]:
    schema = model.model_json_schema()
    conditions: list[dict[str, Any]] = []
    if issubclass(model, BaseSourceArgs):
        conditions.append(
            {
                "oneOf": [
                    {
                        "required": ["path"],
                        "properties": {"path": {"type": "string"}, "document_id": {"type": "null"}},
                    },
                    {
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string"},
                            "path": {"type": "null"},
                            "options": {"type": "object", "maxProperties": 0},
                        },
                    },
                ]
            }
        )
    if issubclass(model, XlsxReadArgs):
        conditions.append(
            {
                "anyOf": [
                    {"properties": {"range_spec": {"type": "null"}}},
                    {"required": ["sheet"], "properties": {"sheet": {"type": "string"}}},
                ]
            }
        )
    if issubclass(model, QueryArgs):
        conditions.append(
            {
                "anyOf": [
                    {"required": ["table_id"], "properties": {"table_id": {"type": "string"}}},
                    {
                        "required": ["sheet", "range_spec", "header_row"],
                        "properties": {
                            "sheet": {"type": "string"},
                            "range_spec": {"type": "string"},
                            "header_row": {"type": "integer"},
                        },
                    },
                ]
            }
        )
    if conditions:
        schema["allOf"] = conditions
    if issubclass(model, ResultArgs):
        length = schema["properties"]["length"]
        for variant in length["anyOf"]:
            if variant.get("type") == "integer":
                variant["maximum"] = config.max_chunk_size
        length["description"] = (
            "Requested characters for text or bytes for binary; null/omitted uses the published default. "
            "The host reply budget can reduce the actual length. Continue using next_offset."
        )
        schema["x-doctokens-result-limits"] = result_limits(config)
    return schema
