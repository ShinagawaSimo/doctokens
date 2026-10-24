"""Concurrent document ownership with short cache locks and cooperative cancellation."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from doctokens_core.execution import ParseCancelled, ParseControl, checkpoint, parse_scope
from doctokens_core.package import PackageError
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
from .search_cache import SearchCache
from .sessions import session_bytes

logger = logging.getLogger(__name__)


class ToolRuntime:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active: set[ParseControl] = set()
        self._closed = False
        self._documents = DocumentStore(config, self._lock)
        self._results = ResultStore(config)
        self._searches = SearchCache(config)
        self._documents.before_remove = self._release_caches
        self._documents.before_session = self._searches.release
        self._presenter = Presenter(config, self._results)
        self._operations = Operations(self._documents, self._presenter, self._searches)
        self._executor = ThreadPoolExecutor(max_workers=config.workers, thread_name_prefix="doctokens")
        self._stop = threading.Event()
        self._maintenance = threading.Thread(target=self._maintain, name="doctokens-expiry", daemon=True)
        self._maintenance.start()

    def _release_caches(self, identifier: str) -> None:
        self._searches.release(identifier)
        self._results.release(identifier)

    def _maintain(self) -> None:
        interval = max(0.05, min(30, self.config.idle_seconds, self.config.result_idle_seconds))
        while not self._stop.wait(interval):
            with self._lock:
                if self._closed:
                    return
                try:
                    self._documents.expire()
                    self._results.expire(set(self._documents.documents))
                    self._searches.expire(set(self._documents.documents))
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

    def _info(self) -> ToolResponse:
        with self._searches.lock:
            search_states = len(self._searches.entries)
            search_bytes = self._searches.bytes
        return ToolResponse(
            {
                "allowed_roots": [str(root) for root in self.config.allowed_roots],
                "result_limits": result_limits(self.config),
                "ocr_available": self.config.ocr_provider is not None,
                "documents": len(self._documents.documents),
                "sessions": sum(d.session is not None for d in self._documents.documents.values()),
                "loading_sessions": sum(d.session_loading for d in self._documents.documents.values()),
                "snapshot_bytes": self._documents.bytes,
                "pending_snapshot_bytes": self._documents.pending_bytes,
                "session_estimated_bytes": session_bytes(self._documents.documents.values()),
                "session_memory_limits": {
                    "per_session": self.config.max_session_memory_bytes,
                    "total": self.config.max_session_total_memory_bytes,
                    "unit": "estimated bytes; not process RSS",
                },
                "mcp_output_mode": self.config.mcp_output_mode,
                "result_bytes": self._results.bytes,
                "search_states": search_states,
                "search_estimated_bytes": search_bytes,
                "search_limits": {
                    "bytes": self.config.max_search_bytes,
                    "states": self.config.max_search_states,
                    "idle_seconds": self.config.search_idle_seconds,
                },
                "configuration": "fixed for this runtime; restart to apply host configuration changes",
            }
        )

    def _dispatch(self, tool_name: str, arguments: dict[str, Any]) -> ToolResponse:
        definition = OPERATIONS.get(tool_name)
        if definition is None:
            raise ToolError("UNKNOWN_TOOL", f"unknown tool {tool_name!r}")
        args = definition[0].model_validate(arguments)
        with self._lock:
            if self._closed:
                raise ToolError("RUNTIME_CLOSED", "create a new runtime before calling tools")
            self._documents.expire()
            self._results.expire(set(self._documents.documents))
            self._searches.expire(set(self._documents.documents))
            if isinstance(args, RuntimeInfoArgs):
                return self._info()
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
                self._documents.remove(identifier)
                return ToolResponse({"document_id": identifier, "released": True})
        with self._documents.acquire(args) as document:
            while not document.operation_lock.acquire(timeout=0.05):
                checkpoint("waiting for document")
            try:
                checkpoint("reading document")
                response = self._operations.run(tool_name, document, args)
                checkpoint("request complete")
                return response
            finally:
                document.operation_lock.release()

    def execute(self, tool_name: str, arguments: dict[str, Any], *, control: ParseControl | None = None) -> ToolResponse:
        context = control or ParseControl()
        with self._lock:
            if self._closed:
                return ToolResponse(error={"code": "RUNTIME_CLOSED", "message": "create a new runtime before calling tools"})
            self._active.add(context)
        success = False
        try:
            with parse_scope(context):
                response = self._dispatch(tool_name, arguments)
                success = not response.is_error
                return response
        except ParseCancelled:
            return ToolResponse(
                error={"code": "CANCELLED", "message": "request cancelled; completed snapshot data remains available"}
            )
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
        finally:
            self._results.finish_operation(context.id, success=success)
            with self._condition:
                self._active.discard(context)
                self._condition.notify_all()

    async def aexecute(self, tool_name: str, arguments: dict[str, Any], *, control: ParseControl | None = None) -> ToolResponse:
        context = control or ParseControl()
        if tool_name in {"get_runtime_info", "read_result", "release_document"}:
            return self.execute(tool_name, arguments, control=context)
        with self._lock:
            if self._closed:
                return ToolResponse(error={"code": "RUNTIME_CLOSED", "message": "tool runtime is closed"})
            future = asyncio.get_running_loop().run_in_executor(
                self._executor, partial(self.execute, tool_name, arguments, control=context)
            )
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            context.cancel()
            raise

    def read_result_resource(self, identifier: str) -> BinaryAttachment:
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
        return self.read_result_resource(identifier)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            for context in self._active:
                context.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)
        with self._condition:
            while self._active:
                self._condition.wait(timeout=0.05)
            self._results.close()
            self._searches.close()
            self._documents.close()
        self._maintenance.join()
