from typing import Any, Dict, Iterable, List, Sequence, Union

from Tools.Installation.tool_base import Tool
from Remote.run_remote_workflow import RemoteWorkflowRunner
from Remote.utilities.config_loader import load_server_ini, load_yaml

DEFAULT_SETTINGS_PATH = "Remote/config/settings.yaml"
DEFAULT_SERVERS_PATH = "Remote/config/servers.ini"


def _normalize_targets(targets: Union[str, Sequence[str], None]) -> List[str]:
    if targets is None:
        return []
    if isinstance(targets, str):
        items = [part.strip() for part in targets.split(",")]
        return [item for item in items if item]
    if isinstance(targets, Iterable):
        return [str(item).strip() for item in targets if str(item).strip()]
    return []


class RemoteWorkflowTool(Tool):
    """Execute the remote pre-install/install/post-install workflow across one or more hosts."""

    def __init__(self) -> None:
        super().__init__(
            name="remote_workflow",
            description=(
                "Run remote Java + Tomcat provisioning using YAML/INI configuration. "
                "Defaults: settings=Remote/config/settings.yaml, servers=Remote/config/servers.ini"
            ),
            parameters={
                "settings_path": {
                    "type": "str",
                    "description": "Path to YAML configuration file (default: Remote/config/settings.yaml)",
                },
                "servers_path": {
                    "type": "str",
                    "description": "Path to server inventory INI file (default: Remote/config/servers.ini)",
                },
                "target_servers": {
                    "type": "list[str] | str",
                    "description": "Optional subset of server names/hosts to run (comma-separated string or array)",
                },
            },
        )

    def run(
        self,
        settings_path: str = DEFAULT_SETTINGS_PATH,
        servers_path: str = DEFAULT_SERVERS_PATH,
        target_servers: Union[str, Sequence[str], None] = None,
    ) -> Dict[str, Any]:
        try:
            settings = load_yaml(settings_path)
            servers = load_server_ini(servers_path)
        except Exception as exc:
            return self._failure(
                f"Unable to load configuration: {exc}",
                command=f"remote_workflow(settings={settings_path}, servers={servers_path})",
            )

        targets = set(_normalize_targets(target_servers))
        if targets:
            servers = [s for s in servers if self._matches_target(s, targets)]
            if not servers:
                return self._failure(
                    "No servers matched the requested target list.",
                    command=f"remote_workflow(settings={settings_path}, servers={servers_path})",
                )

        runner = RemoteWorkflowRunner(settings)
        aggregated: List[Dict[str, Any]] = []
        overall_success = True

        for server in servers:
            try:
                result = runner.run_for_server(server)
            except Exception as exc:  # pragma: no cover - defensive network handling
                result = {
                    "server": server.get("name", server.get("host", "unknown")),
                    "error": {
                        "status": "Failed",
                        "details": f"Execution error: {exc}",
                    },
                }
            aggregated.append(result)
            if not self._is_success_result(result):
                overall_success = False

        output = self._format_summary(aggregated)
        status = "Success" if overall_success else "Failed"
        details = (
            f"Remote workflow executed for {len(aggregated)} server(s)."
            if aggregated
            else "Remote workflow executed with no matching servers."
        )

        return {
            "status": status,
            "command": f"remote_workflow(settings={settings_path}, servers={servers_path})",
            "output": output,
            "details": details,
            "results": aggregated,
        }

    def _failure(self, message: str, command: str) -> Dict[str, Any]:
        return {
            "status": "Failed",
            "command": command,
            "output": message,
            "details": message,
        }

    def _matches_target(self, server: Dict[str, Any], targets: Iterable[str]) -> bool:
        name = server.get("name") or server.get("host")
        host = server.get("host")
        candidates = {str(name).strip().lower(), str(host).strip().lower()}
        return any(target.lower() in candidates for target in targets)

    def _is_success_result(self, result: Dict[str, Any]) -> bool:
        for value in result.values():
            if isinstance(value, dict):
                status = value.get("status")
                if status and status not in {"Success", "Skipped"}:
                    return False
        return True

    def _format_summary(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No servers processed."

        lines: List[str] = []
        for result in results:
            server_name = result.get("server", "<unknown>")
            lines.append(f"Server: {server_name}")
            for key, value in result.items():
                if key == "server":
                    continue
                if isinstance(value, dict):
                    status = value.get("status", "n/a")
                    details = value.get("details")
                    lines.append(f"  {key}: {status}")
                    if details:
                        lines.append(f"    details: {details}")
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        return "\n".join(lines).strip()
