"""Uninstall Apache Tomcat on a remote host."""

from __future__ import annotations

import shlex
from typing import Any, Dict, List

from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool


class RemoteTomcatUninstallTool(RemoteTool):
    """Remove a Tomcat installation from a remote Windows or Linux host."""

    config_path = ("install", "tomcat_uninstall")

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_uninstall",
            description="Uninstall Apache Tomcat remotely (Windows/Linux)",
            parameters={},
            user_parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Path to the Tomcat installation directory to remove",
                },
                "cleanup_logs": {
                    "type": "bool",
                    "description": "Remove log files directory (defaults from settings)",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        tomcat_home: str | None = None,
        cleanup_logs: bool | None = None,
    ) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            os_type = executor.detect_os()
            logs.append(f"Detected OS: {os_type}")

            os_cfg = config.get(os_type, {}) if isinstance(config, dict) else {}
            tomcat_home = tomcat_home or os_cfg.get("tomcat_home") or config.get("tomcat_home")
            if not tomcat_home:
                return self._failure("Tomcat home directory not supplied", logs)

            cleanup_default = os_cfg.get("cleanup_logs")
            if cleanup_default is None:
                cleanup_default = config.get("cleanup_logs", True)
            cleanup_choice = cleanup_logs if cleanup_logs is not None else cleanup_default

            if os_type == "windows":
                logs_dir = os_cfg.get("logs_dir") or config.get("logs_dir")
                return self._uninstall_windows(executor, tomcat_home, logs_dir, bool(cleanup_choice), logs)
            if os_type == "linux":
                logs_dir = os_cfg.get("logs_dir") or config.get("logs_dir")
                return self._uninstall_linux(executor, tomcat_home, logs_dir, bool(cleanup_choice), logs)

            return self._failure("Unsupported operating system", logs)

        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    # ------------------------------------------------------------------
    # Windows uninstall flow
    # ------------------------------------------------------------------
    def _uninstall_windows(
        self,
        executor: RemoteExecutor,
        tomcat_home: str,
        logs_dir: str | None,
        cleanup_logs: bool,
        logs: List[str],
    ) -> Dict[str, Any]:
        logs.append(f"Removing directory {tomcat_home}")
        literal = tomcat_home.replace("'", "''")
        command = (
            "powershell -NoProfile -Command "
            f"if (Test-Path -LiteralPath '{literal}') "
            f"{{ Remove-Item -LiteralPath '{literal}' -Recurse -Force }}"
        )
        stdout, stderr = executor.run(command)
        if stdout.strip():
            logs.append(stdout.strip())
        if stderr.strip():
            logs.append(f"stderr: {stderr.strip()}")

        if cleanup_logs and logs_dir:
            logs.append(f"Removing logs directory {logs_dir}")
            literal_logs = logs_dir.replace("'", "''")
            logs_command = (
                "powershell -NoProfile -Command "
                f"if (Test-Path -LiteralPath '{literal_logs}') "
                f"{{ Remove-Item -LiteralPath '{literal_logs}' -Recurse -Force }}"
            )
            stdout, stderr = executor.run(logs_command)
            if stdout.strip():
                logs.append(stdout.strip())
            if stderr.strip():
                logs.append(f"stderr: {stderr.strip()}")

        return {
            "name": self.name,
            "status": "Success",
            "command": f"Remove Tomcat at {tomcat_home}",
            "output": "\n".join(logs),
            "details": f"Removed Tomcat directory {tomcat_home}",
        }

    # ------------------------------------------------------------------
    # Linux uninstall flow
    # ------------------------------------------------------------------
    def _uninstall_linux(
        self,
        executor: RemoteExecutor,
        tomcat_home: str,
        logs_dir: str | None,
        cleanup_logs: bool,
        logs: List[str],
    ) -> Dict[str, Any]:
        logs.append(f"Removing directory {tomcat_home}")
        home_literal = shlex.quote(tomcat_home)
        stdout, stderr = executor.run(f"rm -rf {home_literal}")
        if stdout.strip():
            logs.append(stdout.strip())
        if stderr.strip():
            logs.append(f"stderr: {stderr.strip()}")

        if cleanup_logs and logs_dir:
            logs.append(f"Removing logs directory {logs_dir}")
            logs_literal = shlex.quote(logs_dir)
            stdout, stderr = executor.run(f"rm -rf {logs_literal}")
            if stdout.strip():
                logs.append(stdout.strip())
            if stderr.strip():
                logs.append(f"stderr: {stderr.strip()}")

        return {
            "name": self.name,
            "status": "Success",
            "command": f"Remove Tomcat at {tomcat_home}",
            "output": "\n".join(logs),
            "details": f"Removed Tomcat directory {tomcat_home}",
        }

    def _failure(self, message: str, logs: List[str]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "output": "\n".join(logs),
            "details": message,
        }
