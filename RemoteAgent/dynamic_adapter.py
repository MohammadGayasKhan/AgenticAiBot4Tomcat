"""Adapters that expose remote tools to chat interfaces without static wiring."""

from __future__ import annotations

import copy
import inspect
from typing import Any, Dict, Iterable, List, Optional, Tuple

from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool
from Remote.utilities.config_loader import load_server_ini, load_yaml

DEFAULT_SETTINGS_PATH = "Remote/config/settings.yaml"
DEFAULT_SERVERS_PATH = "Remote/config/servers.ini"

BASE_PARAMETER_SCHEMA: Dict[str, Dict[str, Any]] = {
    "server": {
        "type": "str",
        "description": "Identifier from servers.ini (name or host). Required unless host+username provided.",
    },
    "settings_path": {
        "type": "str",
        "description": "Optional override for YAML settings file path.",
        "optional": True,
    },
    "servers_path": {
        "type": "str",
        "description": "Optional override for servers.ini inventory path.",
        "optional": True,
    },
    "host": {
        "type": "str",
        "description": "Override host/address (used when server not present in inventory).",
        "optional": True,
    },
    "username": {
        "type": "str",
        "description": "Override username (used when server not present in inventory).",
        "optional": True,
    },
    "password": {
        "type": "str",
        "description": "Optional password override.",
        "optional": True,
    },
    "key_path": {
        "type": "str",
        "description": "Optional private key path for SSH authentication.",
        "optional": True,
    },
}


class DynamicRemoteToolAdapter:
    """Wrap a RemoteTool to handle configuration, server selection, and execution."""

    def __init__(self, tool: RemoteTool) -> None:
        self.tool = tool
        self.name = tool.name
        self.description = tool.description
        self.config_path = tool.get_config_path()

    # ------------------------------------------------------------------
    # Public interface expected by chat agents
    # ------------------------------------------------------------------
    def get_info(self) -> Dict[str, Any]:
        exposed_parameters = dict(BASE_PARAMETER_SCHEMA)
        for key, value in self.tool.get_user_parameters().items():
            exposed_parameters[key] = value
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": exposed_parameters,
        }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        params = dict(kwargs)
        settings_path = params.pop("settings_path", DEFAULT_SETTINGS_PATH)
        servers_path = params.pop("servers_path", DEFAULT_SERVERS_PATH)

        try:
            settings = load_yaml(settings_path) if settings_path else {}
        except Exception as exc:
            return self._failure(f"Unable to load settings YAML: {exc}")

        try:
            servers = load_server_ini(servers_path) if servers_path else []
        except FileNotFoundError:
            servers = []
        except Exception as exc:
            return self._failure(f"Unable to load server inventory: {exc}")

        server_identifier = params.pop("server", None)
        host_override = params.pop("host", None)
        username_override = params.pop("username", None)
        password_override = params.pop("password", None)
        key_path_override = params.pop("key_path", None)

        server_info = _select_server(servers, server_identifier, host_override, username_override)
        if not server_info:
            if host_override and username_override:
                server_info = {
                    "name": host_override,
                    "host": host_override,
                    "username": username_override,
                }
            else:
                return self._failure(
                    "Server not found. Provide host/username overrides or update servers.ini."
                )

        if host_override:
            server_info["host"] = host_override
        if username_override:
            server_info["username"] = username_override
        if password_override is not None:
            server_info["password"] = password_override
        if key_path_override is not None:
            server_info["key_path"] = key_path_override

        if not server_info.get("host") or not server_info.get("username"):
            return self._failure("Missing host or username for remote connection.")

        config_scope = _resolve_config(settings, self.config_path)
        config = copy.deepcopy(config_scope) if isinstance(config_scope, dict) else {}

        executor = RemoteExecutor(
            host=server_info["host"],
            username=server_info["username"],
            password=server_info.get("password") or None,
            key_path=server_info.get("key_path") or None,
        )

        try:
            executor.connect()
        except Exception as exc:  # pragma: no cover - network dependent
            return self._failure(f"Unable to connect to {server_info['host']}: {exc}")

        try:
            call_kwargs = self._build_call_kwargs(self.tool, executor, config, server_info, params)
            result = self.tool.run(**call_kwargs)
            if isinstance(result, dict):
                result.setdefault("target_server", server_info.get("name", server_info.get("host")))
            return result
        except Exception as exc:  # pragma: no cover - defensive execution guard
            return self._failure(f"Execution error: {exc}")
        finally:
            executor.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_call_kwargs(
        self,
        tool: RemoteTool,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        server_info: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        sig = inspect.signature(tool.run)
        kwargs: Dict[str, Any] = {}
        remaining = dict(params)

        for name, parameter in list(sig.parameters.items())[1:]:  # skip self
            if name == "executor":
                kwargs[name] = executor
                continue
            if name == "config":
                kwargs[name] = config
                continue
            if name == "server":
                kwargs[name] = server_info
                continue
            if name == "tomcat_home":
                tomcat_home = remaining.pop("tomcat_home", None)
                if tomcat_home is None:
                    tomcat_home = config.get("tomcat_home") or config.get("default_tomcat_home")
                if tomcat_home is None and parameter.default is inspect._empty:
                    raise ValueError(
                        "tomcat_home not provided. Supply via parameters or settings under post_install.tomcat_* or post_install.default_tomcat_home."
                    )
                kwargs[name] = tomcat_home
                continue

            if name in remaining:
                raw_value = remaining.pop(name)
                converted = _coerce_value(raw_value, parameter.annotation)
                kwargs[name] = converted
            elif name in config:
                kwargs[name] = config[name]
            elif parameter.default is inspect._empty:
                raise ValueError(f"Missing required parameter '{name}' for tool '{tool.name}'")

        if remaining and isinstance(config, dict):
            for key, value in remaining.items():
                reference = config.get(key)
                if reference is not None:
                    config[key] = _coerce_like(reference, value)
                else:
                    config[key] = value

        return kwargs

    def _failure(self, message: str) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "details": message,
        }


# ----------------------------------------------------------------------
# Standalone helpers
# ----------------------------------------------------------------------

def _select_server(
    servers: Iterable[Dict[str, Any]],
    identifier: Optional[str],
    host_override: Optional[str],
    username_override: Optional[str],
) -> Optional[Dict[str, Any]]:
    ident = (identifier or "").strip().lower()
    for record in servers:
        name = str(record.get("name", "")).lower()
        host = str(record.get("host", "")).lower()
        if ident and ident in {name, host}:
            return dict(record)
    if host_override and username_override:
        host_norm = host_override.strip().lower()
        for record in servers:
            if str(record.get("host", "")).lower() == host_norm:
                return dict(record)
    return None


def _resolve_config(settings: Dict[str, Any], path: Tuple[str, ...]) -> Dict[str, Any]:
    cursor: Any = settings
    for key in path:
        if not isinstance(cursor, dict):
            return {}
        cursor = cursor.get(key, {})
    return cursor if isinstance(cursor, dict) else {}


def _coerce_value(value: Any, annotation: Any) -> Any:
    target = _resolve_primitive(annotation)
    if target is None:
        return value
    try:
        if target is bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "1"}:
                    return True
                if lowered in {"false", "no", "0"}:
                    return False
            return bool(value)
        return target(value)
    except Exception:
        return value


def _resolve_primitive(annotation: Any) -> Optional[type]:
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if annotation in {int, float, bool, str}:
        return annotation  # type: ignore[return-value]
    if origin in {list, tuple, set}:
        return None
    if origin is not None and args:
        for arg in args:
            primitive = _resolve_primitive(arg)
            if primitive is not None:
                return primitive
    if annotation is inspect._empty:
        return None
    if isinstance(annotation, type) and annotation in {int, float, bool, str}:
        return annotation
    return None


def _coerce_like(reference: Any, value: Any) -> Any:
    if isinstance(reference, bool):
        return _coerce_value(value, bool)
    if isinstance(reference, int) and not isinstance(reference, bool):
        return _coerce_value(value, int)
    if isinstance(reference, float):
        return _coerce_value(value, float)
    if isinstance(reference, str):
        return str(value)
    return value
