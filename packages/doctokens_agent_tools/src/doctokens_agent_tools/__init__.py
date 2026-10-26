"""Office tools with a shared runtime for direct calls and optional MCP."""

from doctokens_core.runtime.execution import ParseCancelled, ParseControl

from .contracts.config import RuntimeConfig
from .contracts.models import BinaryAttachment, ToolDefinition, ToolResponse
from .runtime.engine import ToolRuntime

__version__ = "0.1.0"

__all__ = [
    "BinaryAttachment",
    "ParseCancelled",
    "ParseControl",
    "RuntimeConfig",
    "ToolDefinition",
    "ToolResponse",
    "ToolRuntime",
]
