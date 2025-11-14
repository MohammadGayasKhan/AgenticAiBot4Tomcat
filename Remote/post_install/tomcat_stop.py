"""Remote tool for stopping Apache Tomcat."""

from __future__ import annotations

from typing import Any, Dict, List

from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool


class RemoteTomcatStopTool(RemoteTool):
    """Stop Apache Tomcat on a remote host."""

    config_path = ("post_install", "tomcat_stop")

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_stop",
            description="Stop Apache Tomcat remotely (Windows/Linux)",
            parameters={},
            user_parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Tomcat home directory on the remote host",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        tomcat_home: str | None = None,
    ) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            os_type = executor.detect_os()
            logs.append(f"Detected OS: {os_type}")

            os_cfg = config.get(os_type, {}) if isinstance(config, dict) else {}
            tomcat_home = tomcat_home or os_cfg.get("tomcat_home") or config.get("tomcat_home")
            if not tomcat_home:
                return self._failure("Tomcat home directory not supplied", logs)

            command_template = os_cfg.get("stop_command") or config.get("stop_command")
            if not command_template:
                return self._failure("stop_command not configured", logs)

            command = command_template.format(tomcat_home=tomcat_home)
            logs.append(f"Executing stop command: {command}")

            stdout, stderr = executor.run(command)
            if stdout.strip():
                logs.append(stdout.strip())
            if stderr.strip():
                logs.append(f"stderr: {stderr.strip()}")

            status = "Success" if not stderr.strip() else "Warning"
            details = "Tomcat stop command executed"
            if status != "Success":
                details = f"Tomcat stop command completed with stderr: {stderr.strip()}"

            return {
                "name": self.name,
                "status": status,
                "command": command,
                "output": "\n".join(logs),
                "details": details,
                "tomcat_home": tomcat_home,
            }

        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    def _failure(self, message: str, logs: List[str]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": "remote_tomcat_stop",
            "output": "\n".join(logs),
            "details": message,
        }
