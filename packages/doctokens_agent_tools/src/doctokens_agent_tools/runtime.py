"""Reusable, context-managed entry point for direct tool calls and MCP."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ooxml_llm_core.package import PackageError
from pydantic import ValidationError

from .catalog import OPERATIONS, definitions
from .config import RuntimeConfig
from .contracts import result_limits
from .documents import DocumentStore
from .models import BinaryAttachment, ToolDefinition, ToolError, ToolResponse
from .operations import Operations
from .presentation import Presenter
from .results import ResultStore
from .schemas import BaseSourceArgs, ResultArgs, RuntimeInfoArgs

logger = logging.getLogger(__name__)


class ToolRuntime:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._closed = False
        self._documents = DocumentStore(config)
        self._results = ResultStore(config)
        self._presenter = Presenter(config, self._results)
        self._operations = Operations(self._documents, self._presenter)
        self._executor = ThreadPoolExecutor(max_workers=config.workers, thread_name_prefix="doctokens")
        self._stop = threading.Event()
        self._maintenance = threading.Thread(target=self._maintain, name="doctokens-expiry", daemon=True)
        self._maintenance.start()

    def _maintain(self) -> None:
        interval = max(0.05, min(30, self.config.idle_seconds, self.config.result_idle_seconds))
        while not self._stop.wait(interval):
            with self._lock:
                if self._closed:
                    return
                try:
                    self._documents.expire()
                    self._results.expire(set(self._documents.documents))
                except Exception:
                    logger.exception("tool cache maintenance failed")

    def __enter__(self) -> ToolRuntime:
        if self._closed:
            raise RuntimeError("tool runtime is closed")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def list_tools(self) -> list[ToolDefinition]:
        return definitions(self.config)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResponse:
        with self._lock:
            try:
                if self._closed:
                    raise ToolError("RUNTIME_CLOSED", "create a new runtime before calling tools")
                definition = OPERATIONS.get(tool_name)
                if definition is None:
                    raise ToolError("UNKNOWN_TOOL", f"unknown tool {tool_name!r}")
                args = definition[0].model_validate(arguments)
                self._documents.expire()
                self._results.expire(set(self._documents.documents))
                if isinstance(args, RuntimeInfoArgs):
                    return ToolResponse(
                        {
                            "allowed_roots": [str(root) for root in self.config.allowed_roots],
                            "result_limits": result_limits(self.config),
                            "ocr_available": self.config.ocr_provider is not None,
                            "documents": len(self._documents.documents),
                            "sessions": sum(d.session is not None for d in self._documents.documents.values()),
                            "snapshot_bytes": self._documents.bytes,
                            "result_bytes": self._results.bytes,
                            "configuration": "fixed for this runtime; restart to apply host configuration changes",
                        }
                    )
                if isinstance(args, ResultArgs):
                    response = self._presenter.fragment(args.result_id, args.offset, args.length)
                    identifier = self._results.get(args.result_id).document_id
                    self._documents.documents[identifier].touched = time.monotonic()
                    return response
                assert isinstance(args, BaseSourceArgs)
                if tool_name == "release_document":
                    document = self._documents.lookup(args)
                    if document is None:
                        return ToolResponse({"released": False})
                    identifier = document.id
                    self._results.release(identifier)
                    self._documents.remove(identifier)
                    return ToolResponse({"document_id": identifier, "released": True})
                with self._documents.acquire(args) as document:
                    return self._operations.run(tool_name, document, args)
            except ValidationError as exc:
                errors = exc.errors(include_url=False, include_input=False, include_context=False)
                details = [{"field": ".".join(map(str, error["loc"])), "message": error["msg"]} for error in errors[:8]]
                message = "; ".join(f"{item['field'] or 'arguments'}: {item['message']}" for item in details[:3])
                return ToolResponse(error={"code": "INVALID_ARGUMENT", "message": message, "details": details})
            except ToolError as exc:
                return ToolResponse(error={"code": exc.code, "message": str(exc)})
            except PackageError as exc:
                return ToolResponse(error={"code": "INVALID_DOCUMENT", "message": str(exc)})
            except KeyError as exc:
                resource_operation = tool_name == "read_resource" or tool_name.startswith("render_")
                code = "RESOURCE_NOT_FOUND" if resource_operation else "INVALID_ARGUMENT"
                return ToolResponse(error={"code": code, "message": str(exc)})
            except (ValueError, TypeError) as exc:
                return ToolResponse(error={"code": "INVALID_ARGUMENT", "message": str(exc)})
            except OSError as exc:
                return ToolResponse(error={"code": "IO_ERROR", "message": str(exc)})
            except Exception:
                logger.exception("tool execution failed: %s", tool_name)
                return ToolResponse(error={"code": "INTERNAL_ERROR", "message": "unexpected tool failure; inspect server stderr"})

    async def aexecute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResponse:
        if self._closed:
            return ToolResponse(error={"code": "RUNTIME_CLOSED", "message": "tool runtime is closed"})
        return await asyncio.get_running_loop().run_in_executor(self._executor, self.execute, tool_name, arguments)

    def read_result_resource(self, identifier: str) -> BinaryAttachment:
        """Explicit binary-resource transport sharing result and document lifetimes."""
        with self._lock:
            if self._closed:
                raise ToolError("RUNTIME_CLOSED", "tool runtime is closed")
            self._documents.expire()
            self._results.expire(set(self._documents.documents))
            result = self._results.get(identifier)
            if not isinstance(result.value, bytes):
                raise ToolError("INVALID_ARGUMENT", "resource URI requires a binary result")
            self._documents.documents[result.document_id].touched = time.monotonic()
            return BinaryAttachment(result.value, result.metadata.get("media_type", "application/octet-stream"))

    async def aread_result_resource(self, identifier: str) -> BinaryAttachment:
        if self._closed:
            raise ToolError("RUNTIME_CLOSED", "tool runtime is closed")
        return await asyncio.get_running_loop().run_in_executor(self._executor, self.read_result_resource, identifier)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            self._results.close()
            self._documents.close()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._maintenance.join()
