"""Select one markup-compatibility branch before DOCX content dispatch."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO, cast
from xml.etree import ElementTree as ET

from ..model import AssetLookup, ParseWarning, append_warning
from .compatibility_support import SUPPORTED_NAMESPACES, can_process, child_context

_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_ALTERNATE = _MC + "AlternateContent"
_CHOICE = _MC + "Choice"
_FALLBACK = _MC + "Fallback"


@dataclass
class _PartState:
    part: str
    indices: dict[ET.Element, int] = field(default_factory=dict)
    requirements: dict[ET.Element, dict[str, str | None]] = field(default_factory=dict)


@dataclass
class _Expansion:
    nodes: list[ET.Element]
    records: list[dict[str, object]] = field(default_factory=list)
    complete: bool = True


class DocxCompatibility:
    """Per-parse selection records; no global cache or speculative parser effects."""

    def __init__(self, warnings: list[ParseWarning], assets: AssetLookup) -> None:
        self.warnings = warnings
        self.assets = assets
        self.records: list[dict[str, object]] = []

    def iter_events(self, stream: IO[bytes], part: str) -> Iterator[tuple[str, ET.Element]]:
        """Keep normal streaming events; buffer only an AlternateContent subtree.

        Namespace bindings are captured while they are in scope. Selected events
        are replayed without MC wrappers so even a body-level branch uses the
        normal block parser. Unselected branches never reach content dispatch.
        """
        state = _PartState(part)
        stack: list[ET.Element] = []
        scopes: list[dict[str, str]] = [{}]
        contexts = ["other"]
        pending: dict[str, str] = {}
        alternate_depth: int | None = None
        ordinal = 0
        for event, payload in ET.iterparse(stream, events=("start-ns", "start", "end")):
            if event == "start-ns":
                prefix, uri = cast(tuple[str, str], payload)
                pending[prefix] = uri
                continue
            element = cast(ET.Element, payload)
            if event == "start":
                scopes.append({**scopes[-1], **pending} if pending else scopes[-1])
                pending.clear()
                stack.append(element)
                contexts.append(child_context(element.tag, contexts[-1]))
                if element.tag == _ALTERNATE:
                    ordinal += 1
                    state.indices[element] = ordinal
                    if alternate_depth is None:
                        alternate_depth = len(stack)
                elif element.tag == _CHOICE and alternate_depth is not None:
                    state.requirements[element] = {
                        prefix: scopes[-1].get(prefix) for prefix in element.get("Requires", "").split()
                    }
                if alternate_depth is None:
                    yield event, element
                continue
            if alternate_depth == len(stack):
                context = contexts[-2]
                expanded = self._select(element, context, state)
                if len(stack) > 1:
                    parent = stack[-2]
                    index = list(parent).index(element)
                    parent[index : index + 1] = expanded.nodes
                self.records.extend(expanded.records)
                for record in expanded.records:
                    if record["branch"] == "none":
                        append_warning(
                            self.warnings,
                            "ALTERNATE_CONTENT_UNRESOLVED",
                            "No processable Choice or Fallback in AlternateContent.",
                            part=part,
                            block_id=f"AlternateContent[{record['index']}]",
                        )
                for selected in expanded.nodes:
                    yield from _events(selected)
                state.indices.clear()
                state.requirements.clear()
                alternate_depth = None
            elif alternate_depth is None:
                yield event, element
            stack.pop()
            scopes.pop()
            contexts.pop()

    def read(self, stream: IO[bytes], part: str) -> ET.Element:
        """Build an ancillary tree using the same selection and namespace rules."""
        root = None
        for _event, element in self.iter_events(stream, part):
            if root is None:
                root = element
        if root is None:
            raise ET.ParseError("empty XML part")
        return root

    def _expand(self, nodes: list[ET.Element], context: str, state: _PartState) -> _Expansion:
        expanded = _Expansion([])
        for node in nodes:
            if node.tag == _ALTERNATE:
                nested = self._select(node, context, state)
            else:
                nested = self._expand(list(node), child_context(node.tag, context), state)
                node[:] = nested.nodes
                nested.nodes = [node]
            expanded.nodes.extend(nested.nodes)
            expanded.records.extend(nested.records)
            expanded.complete &= nested.complete
        return expanded

    def _select(self, alternate: ET.Element, context: str, state: _PartState) -> _Expansion:
        rejected: list[dict[str, object]] = []
        choice_index = 0
        for choice in alternate:
            if choice.tag != _CHOICE:
                continue
            choice_index += 1
            requires = state.requirements.get(choice, {})
            reason = "unsupported_namespace"
            if requires and all(uri in SUPPORTED_NAMESPACES for uri in requires.values()):
                expanded = self._expand(list(choice), context, state)
                if expanded.complete and can_process(expanded.nodes, context, state.part, self.assets):
                    record = self._record(state, alternate, "Choice", "supported_choice", rejected)
                    record.update(choiceIndex=choice_index, requires=requires)
                    expanded.records.insert(0, record)
                    return expanded
                reason = "unprocessable_content"
            elif not requires or any(uri is None for uri in requires.values()):
                reason = "invalid_requires"
            rejected.append({"choiceIndex": choice_index, "requires": requires, "reason": reason})

        fallback = next((branch for branch in alternate if branch.tag == _FALLBACK), None)
        if fallback is not None:
            expanded = self._expand(list(fallback), context, state)
            expanded.complete &= can_process(expanded.nodes, context, state.part, self.assets)
            reason = (
                "choice_unprocessable" if any(r["reason"] == "unprocessable_content" for r in rejected) else "no_supported_choice"
            )
            expanded.records.insert(0, self._record(state, alternate, "Fallback", reason, rejected))
            return expanded
        return _Expansion([], [self._record(state, alternate, "none", "missing_fallback", rejected)], False)

    @staticmethod
    def _record(
        state: _PartState, alternate: ET.Element, branch: str, reason: str, rejected: list[dict[str, object]]
    ) -> dict[str, object]:
        return {
            "part": state.part,
            "index": state.indices[alternate],
            "branch": branch,
            "requires": {},
            "reason": reason,
            "rejectedChoices": rejected,
        }


def _events(node: ET.Element) -> Iterator[tuple[str, ET.Element]]:
    yield "start", node
    # Downstream streaming consumers can clear completed children during replay.
    for child in list(node):
        yield from _events(child)
    yield "end", node
