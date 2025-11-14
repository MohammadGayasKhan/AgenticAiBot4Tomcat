"""Utility tool to list configured remote servers."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from Remote.utilities.config_loader import load_server_ini

DEFAULT_SERVERS_PATH = "Remote/config/servers.ini"
PLACEHOLDER_PREFIXES = ("/path/to", "\\path\\to")


class ServerInventoryTool:
    """Expose the contents of servers.ini so the chatbot can list configured hosts."""

    def __init__(self) -> None:
        self.name = "list_servers"
        self.description = "List the configured remote servers from an INI inventory."
        self.parameters = {
            "servers_path": {
                "type": "str",
                "description": "Path to server inventory INI file (default: Remote/config/servers.ini)",
                "optional": True,
            }
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, servers_path: str = DEFAULT_SERVERS_PATH) -> Dict[str, Any]:
        normalized_path = self._normalize_path(servers_path)
        try:
            servers = load_server_ini(normalized_path)
        except FileNotFoundError:
            return {
                "name": self.name,
                "status": "Failed",
                "details": f"Server inventory not found at {normalized_path}",
                "command": f"load_server_ini({normalized_path})",
            }
        except Exception as exc:
            return {
                "name": self.name,
                "status": "Failed",
                "details": f"Unable to parse inventory: {exc}",
                "command": f"load_server_ini({normalized_path})",
            }

        entries: List[str] = []
        for server in servers:
            name = server.get("name", "<unnamed>")
            host = server.get("host", "<unknown>")
            username = server.get("username", "<unknown>")
            entries.append(f"{name} ({host}) as {username}")

        summary = "\n".join(entries) if entries else "No servers defined."
        return {
            "name": self.name,
            "status": "Success",
            "details": summary,
            "command": f"load_server_ini({normalized_path})",
            "servers": servers,
        }

    def _normalize_path(self, raw_path: str) -> str:
        path = (raw_path or "").strip()
        if not path or any(path.lower().startswith(prefix) for prefix in PLACEHOLDER_PREFIXES):
            path = DEFAULT_SERVERS_PATH

        # Allow callers to refer to workspace-relative paths without leading ./
        if not os.path.isabs(path):
            return path.replace("\\", os.sep).replace("/", os.sep)
        return path
