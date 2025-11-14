"""Dynamic discovery utilities for remote automation tools."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Dict, Iterable, List, Sequence, Type, TypeVar

from Remote import __path__ as REMOTE_PACKAGE_PATH  # type: ignore[attr-defined]
from Remote.tool_base import RemoteTool

T = TypeVar("T", bound=RemoteTool)

# Packages that do not contain tool implementations and can be skipped to speed up discovery.
EXCLUDE_MODULE_PREFIXES: Sequence[str] = (
    "Remote.config",
    "Remote.utilities",
    "Remote.__pycache__",
)


def _should_skip_module(fullname: str) -> bool:
    return any(fullname.startswith(prefix) for prefix in EXCLUDE_MODULE_PREFIXES)


def _iter_remote_modules() -> Iterable[ModuleType]:
    """Yield imported modules under the Remote package that may define tools."""
    for module_info in pkgutil.walk_packages(REMOTE_PACKAGE_PATH, prefix="Remote."):
        fullname = module_info.name
        if _should_skip_module(fullname):
            continue
        try:
            module = importlib.import_module(fullname)
        except Exception:  # pragma: no cover - defensive import guard
            continue
        yield module


def discover_tool_classes() -> List[Type[T]]:
    """Discover all RemoteTool subclasses defined under the Remote package."""
    discovered: Dict[str, Type[T]] = {}
    for module in _iter_remote_modules():
        for _, member in inspect.getmembers(module, inspect.isclass):
            if not issubclass(member, RemoteTool) or member is RemoteTool:
                continue
            if member.__module__ != module.__name__:
                continue
            # Ensure the class can be instantiated without required arguments
            init_signature = inspect.signature(member.__init__)
            parameters = list(init_signature.parameters.values())[1:]  # drop self
            if any(param.default is inspect._empty and param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD}
                   for param in parameters):
                continue
            discovered[member.__name__] = member  # Deduplicate by class name
    return sorted(discovered.values(), key=lambda cls: cls.__name__)


def instantiate_tools() -> List[RemoteTool]:
    """Instantiate all dynamically discovered remote tools."""
    instances: List[RemoteTool] = []
    for tool_cls in discover_tool_classes():
        try:
            instances.append(tool_cls())
        except Exception:  # pragma: no cover - defensive
            continue
    return instances
