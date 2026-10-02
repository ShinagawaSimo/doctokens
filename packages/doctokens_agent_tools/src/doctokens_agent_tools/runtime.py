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
from .documents import DocumentStore
from .models import ToolDefinition, ToolError, ToolResponse
from .operations import Operations
from .presentation import Presenter
from .results import ResultStore
from .schemas import ResultArgs, SourceArgs

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
        return definitions()

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
                if isinstance(args, ResultArgs):
                    response = self._presenter.fragment(args.result_id, args.offset, args.length)
                    identifier = response.data["document_id"]
                    self._documents.documents[identifier].touched = time.monotonic()
                    return response
                assert isinstance(args, SourceArgs)
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
                return ToolResponse(error={"code": "INVALID_ARGUMENT", "message": str(exc)})
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
