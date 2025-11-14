"""Utilities for dynamically discovering remote automation tools."""

from __future__ import annotations

from typing import List

from .dynamic_adapter import DynamicRemoteToolAdapter
from .tool_loader import instantiate_tools


def build_dynamic_remote_tools() -> List[DynamicRemoteToolAdapter]:
    """Instantiate all remote tools and wrap them with dynamic adapters."""
    return [DynamicRemoteToolAdapter(tool) for tool in instantiate_tools()]
