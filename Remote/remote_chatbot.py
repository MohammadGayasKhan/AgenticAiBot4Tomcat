"""Compatibility wrapper exposing the LangChain remote chatbot implementation."""

from __future__ import annotations

from RemoteAgent.chatbot import build_dynamic_remote_tools
from RemoteAgent.langchain_chatbot import RemoteLangChainChatBot

__all__ = ["RemoteLangChainChatBot", "build_dynamic_remote_tools"]
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from chatbot import ChatBot
from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool
from Remote.utilities.config_loader import load_server_ini, load_yaml
from Remote.pre_install import (
    RemoteDiskCheckTool,
    RemoteJavaInstallTool,
    RemotePortCheckTool,
    RemoteRamCheckTool,
)
from Remote.install.remote_tomcat_install import RemoteTomcatInstallTool
from Remote.post_install import (
    RemoteTomcatStartTool,
    RemoteTomcatStopTool,
    RemoteTomcatValidationTool,
)

DEFAULT_SETTINGS_PATH = "Remote/config/settings.yaml"
DEFAULT_SERVERS_PATH = "Remote/config/servers.ini"

InvokeFn = Callable[[RemoteTool, RemoteExecutor, Dict[str, Any], Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class RemoteToolAdapter:
    """Adapter that injects connection/config handling before invoking a remote tool."""

    def __init__(
        self,
        tool: RemoteTool,
        config_path: Sequence[str],
        parameter_schema: Dict[str, Any],
        description_override: Optional[str],
        invoke: InvokeFn,
    ) -> None:
        self.tool = tool
        self.name = tool.name
        self.config_path = tuple(config_path)
        self.parameter_schema = parameter_schema
        self.description = description_override or tool.description
        self._invoke = invoke

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameter_schema,
        }

    def run(
        self,
        server: str,
        settings_path: str = DEFAULT_SETTINGS_PATH,
        servers_path: str = DEFAULT_SERVERS_PATH,
        **overrides: Any,
    ) -> Dict[str, Any]:
        try:
            settings = load_yaml(settings_path)
        except Exception as exc:
            return self._failure(f"Unable to read settings file: {exc}")

        server_records: List[Dict[str, Any]] = []
        try:
            if servers_path:
                server_records = load_server_ini(servers_path)
        except FileNotFoundError:
            server_records = []
        except Exception as exc:
            return self._failure(f"Unable to read server inventory: {exc}")

        host_override = overrides.pop("host", None)
        username_override = overrides.pop("username", None)
        password_override = overrides.pop("password", None)
        key_path_override = overrides.pop("key_path", None)

        server_info = self._select_server(server_records, server, host_override, username_override)
        if not server_info:
            if host_override and username_override:
                server_info = {
                    "name": server or host_override,
                    "host": host_override,
                    "username": username_override,
                }
            else:
                return self._failure(
                    "Server not found; provide credentials via host/username or update servers.ini."
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
            config_section = self._extract_config(settings)
            result = self._invoke(self.tool, executor, config_section, server_info, overrides)
            if isinstance(result, dict):
                result.setdefault("target_server", server_info.get("name"))
            return result
        except Exception as exc:  # pragma: no cover - defensive
            return self._failure(f"Error executing tool: {exc}")
        finally:
            executor.close()

    def _extract_config(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        cursor: Any = settings
        ancestors: List[Dict[str, Any]] = []
        for key in self.config_path:
            if not isinstance(cursor, dict):
                return {}
            ancestors.append(cursor)
            cursor = cursor.get(key, {})

        if not isinstance(cursor, dict):
            return {}

        result: Dict[str, Any] = dict(cursor)
        for ancestor in reversed(ancestors):
            if not isinstance(ancestor, dict):
                continue
            if "default_tomcat_home" in ancestor and "default_tomcat_home" not in result:
                result["default_tomcat_home"] = ancestor["default_tomcat_home"]
                break

        return result

    def _select_server(
        self,
        records: Iterable[Dict[str, Any]],
        identifier: str,
        host_override: Optional[str],
        username_override: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        ident_norm = (identifier or "").strip().lower()
        for record in records:
            name = str(record.get("name", "")).lower()
            host = str(record.get("host", "")).lower()
            if ident_norm in {name, host}:
                return dict(record)
        # Support direct host matching when override values are supplied
        if host_override and username_override:
            host_norm = host_override.strip().lower()
            for record in records:
                if str(record.get("host", "")).lower() == host_norm:
                    return dict(record)
        return None

    def _failure(self, message: str) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "details": message,
        }


class RemoteChatBot(ChatBot):
    """ChatBot variant tailored for remote automation tools."""

    def __init__(self, tools: List[Any]):
        super().__init__(tools)
        self.persona = f"""
            You are Remote SysCheck AI, a remote infrastructure automation assistant.

            You manage remote hosts over SSH/PowerShell sessions and must never perform destructive actions unless explicitly approved.

            Available remote tools and parameter schemas (use exact keys):
            {chr(10).join([str(tool.get_info()) for tool in tools])}

            Always verify a server is reachable before running installation steps.
        """.strip()


def _normalize_port_override(value: Any) -> Optional[List[int]]:
    if value is None:
        return None
    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",") if item.strip()]
        result: List[int] = []
        for item in candidates:
            try:
                result.append(int(item))
            except ValueError:
                continue
        return result or None
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError):
        return None


def _invoke_disk(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    return tool.run(
        executor=executor,
        config=cfg,
        path=params.get("path"),
        min_free_mb=params.get("min_free_mb"),
    )


def _invoke_port(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    return tool.run(
        executor=executor,
        config=cfg,
        ports=_normalize_port_override(params.get("ports")),
    )


def _invoke_ram(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    return tool.run(
        executor=executor,
        config=cfg,
        min_mb=params.get("min_mb"),
    )


def _invoke_java(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    return tool.run(executor=executor, config=cfg)


def _invoke_tomcat_install(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    return tool.run(executor=executor, config=cfg)


def _resolve_tomcat_home(
    cfg: Dict[str, Any],
    params: Dict[str, Any],
    *,
    required: bool,
    config_hint: str,
) -> str | None:
    candidate = (
        params.get("tomcat_home")
        or cfg.get("tomcat_home")
        or cfg.get("default_tomcat_home")
    )
    if required and not candidate:
        raise ValueError(
            "Tomcat home not provided. Supply tomcat_home or configure "
            f"{config_hint}.tomcat_home."
        )
    return candidate


def _invoke_tomcat_start(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    tomcat_home = _resolve_tomcat_home(
        cfg,
        params,
        required=True,
        config_hint="post_install.tomcat_start",
    )
    return tool.run(
        executor=executor,
        config=cfg,
        tomcat_home=tomcat_home,
    )


def _invoke_tomcat_validation(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    effective_cfg = dict(cfg)
    for key in ("port", "host_template", "wait_seconds"):
        if params.get(key) is not None:
            effective_cfg[key] = params[key]

    tomcat_home = _resolve_tomcat_home(
        effective_cfg,
        params,
        required=False,
        config_hint="post_install.tomcat_validation",
    )
    return tool.run(
        executor=executor,
        config=effective_cfg,
        server=server_info,
        tomcat_home=tomcat_home,
    )


def _invoke_tomcat_stop(
    tool: RemoteTool,
    executor: RemoteExecutor,
    cfg: Dict[str, Any],
    server_info: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    tomcat_home = _resolve_tomcat_home(
        cfg,
        params,
        required=True,
        config_hint="post_install.tomcat_stop",
    )
    return tool.run(
        executor=executor,
        config=cfg,
        tomcat_home=tomcat_home,
    )


def _build_remote_tool_adapters() -> List[RemoteToolAdapter]:
    disk_tool = RemoteDiskCheckTool()
    port_tool = RemotePortCheckTool()
    ram_tool = RemoteRamCheckTool()
    java_tool = RemoteJavaInstallTool()
    tomcat_install_tool = RemoteTomcatInstallTool()
    tomcat_start_tool = RemoteTomcatStartTool()
    tomcat_validation_tool = RemoteTomcatValidationTool()
    tomcat_stop_tool = RemoteTomcatStopTool()

    adapters: List[RemoteToolAdapter] = []

    adapters.append(
        RemoteToolAdapter(
            tool=disk_tool,
            config_path=("pre_install", "disk_check"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "path": {"type": "str", "description": "Optional override path or drive (default from settings)"},
                "min_free_mb": {"type": "int", "description": "Optional override minimum free space in MB"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=disk_tool.description,
            invoke=_invoke_disk,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=port_tool,
            config_path=("pre_install", "port_check"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "ports": {"type": "list[int] | str", "description": "Optional override ports (list or comma separated)"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=port_tool.description,
            invoke=_invoke_port,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=ram_tool,
            config_path=("pre_install", "ram_check"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "min_mb": {"type": "int", "description": "Optional override minimum RAM in MB"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=ram_tool.description,
            invoke=_invoke_ram,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=java_tool,
            config_path=("pre_install", "java"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=java_tool.description,
            invoke=_invoke_java,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=tomcat_install_tool,
            config_path=("install", "tomcat"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=tomcat_install_tool.description,
            invoke=_invoke_tomcat_install,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=tomcat_start_tool,
            config_path=("post_install", "tomcat_start"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "tomcat_home": {"type": "str", "description": "Tomcat home directory (optional if provided in settings)"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=tomcat_start_tool.description,
            invoke=_invoke_tomcat_start,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=tomcat_validation_tool,
            config_path=("post_install", "tomcat_validation"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "tomcat_home": {"type": "str", "description": "Tomcat home directory (optional if provided in settings)"},
                "port": {"type": "int", "description": "Override HTTP port", "optional": True},
                "host_template": {"type": "str", "description": "Override host template", "optional": True},
                "wait_seconds": {"type": "int", "description": "Override wait seconds", "optional": True},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=tomcat_validation_tool.description,
            invoke=_invoke_tomcat_validation,
        )
    )

    adapters.append(
        RemoteToolAdapter(
            tool=tomcat_stop_tool,
            config_path=("post_install", "tomcat_stop"),
            parameter_schema={
                "server": {"type": "str", "description": "Server name or host from servers.ini"},
                "tomcat_home": {"type": "str", "description": "Tomcat home directory (optional if provided in settings)"},
                "settings_path": {"type": "str", "description": "Custom YAML settings path", "optional": True},
                "servers_path": {"type": "str", "description": "Custom servers.ini path", "optional": True},
                "host": {"type": "str", "description": "Override host/address", "optional": True},
                "username": {"type": "str", "description": "Override username", "optional": True},
                "password": {"type": "str", "description": "Override password", "optional": True},
                "key_path": {"type": "str", "description": "Override private key path", "optional": True},
            },
            description_override=tomcat_stop_tool.description,
            invoke=_invoke_tomcat_stop,
        )
    )

    return adapters


def _run_cli() -> None:
    adapters = _build_remote_tool_adapters()
    bot = RemoteChatBot(adapters)

    print("Initializing Remote SysCheck AI...\n")
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                print("\nInput closed. Exiting remote chat. Goodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit", "bye"}:
                print("Exiting remote chat. Goodbye!")
                break

            response = bot.perform_task(user_input)
            print(f"Bot: {response}")
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting remote chat. Goodbye!")


if __name__ == "__main__":
    _run_cli()
