"""Remote tool for starting Apache Tomcat."""

from __future__ import annotations

import shlex
from typing import Any, Dict, List

from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool


class RemoteTomcatStartTool(RemoteTool):
    """Start Apache Tomcat on a remote host."""

    config_path = ("post_install", "tomcat_start")

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_start",
            description="Start Apache Tomcat remotely (Windows/Linux)",
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

            if not isinstance(config, dict):
                config = {}
            os_cfg = config.get(os_type, {}) if isinstance(config.get(os_type), dict) else {}

            home = tomcat_home or os_cfg.get("tomcat_home") or config.get("tomcat_home")
            if not home:
                return self._failure("Tomcat home directory not supplied", logs)

            exec_timeout = self._resolve_timeout(os_cfg, config)
            ready_timeout = self._resolve_ready_timeout(os_cfg, config)
            port = self._resolve_port(os_cfg, config)
            logs.append(f"Command timeout set to {exec_timeout:.0f}s")
            logs.append(f"Readiness timeout set to {ready_timeout:.0f}s")
            logs.append(f"Target port: {port}")

            if os_type == "windows":
                return self._start_windows(
                    executor,
                    home,
                    os_cfg,
                    config,
                    exec_timeout,
                    ready_timeout,
                    port,
                    logs,
                )
            if os_type == "linux":
                return self._start_linux(
                    executor,
                    home,
                    os_cfg,
                    config,
                    exec_timeout,
                    ready_timeout,
                    port,
                    logs,
                )

            logs.append("Unsupported operating system detected")
            return self._failure("Unsupported operating system", logs)

        except TimeoutError as exc:
            logs.append(str(exc))
            return self._failure(str(exc), logs)
        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    # ------------------------------------------------------------------
    # Windows implementation
    # ------------------------------------------------------------------
    def _start_windows(
        self,
        executor: RemoteExecutor,
        tomcat_home: str,
        os_cfg: Dict[str, Any],
        cfg: Dict[str, Any],
        exec_timeout: float,
        ready_timeout: float,
        port: int,
        logs: List[str],
    ) -> Dict[str, Any]:
        command_template = os_cfg.get("start_command") or cfg.get("start_command")
        if not command_template:
            # Escape backslashes for PowerShell
            ps_home = tomcat_home.replace("\\", "\\\\")
            # Simple approach: use cmd.exe to run startup.bat in background
            command = (
                f"powershell -NoProfile -Command "
                f"\"if (-not (Test-Path '{ps_home}')) {{ Write-Error 'Tomcat directory not found'; exit 1 }}; "
                f"$bin = '{ps_home}\\bin'; "
                f"$startup = Join-Path $bin 'startup.bat'; "
                f"if (-not (Test-Path $startup)) {{ Write-Error 'startup.bat not found'; exit 1 }}; "
                f"Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $startup -WorkingDirectory $bin -WindowStyle Hidden; "
                f"Start-Sleep -Seconds 3; "
                f"if (Get-Process -Name java -ErrorAction SilentlyContinue) {{ Write-Output 'Tomcat process started' }} else {{ Write-Warning 'Java process not detected yet' }}\""
            )
        else:
            command = command_template.format(tomcat_home=tomcat_home)

        logs.append(f"Executing start command: {command}")
        stdout, stderr = executor.run(command, timeout=exec_timeout)
        if stdout.strip():
            logs.append(stdout.strip())
        if stderr.strip():
            logs.append(f"stderr: {stderr.strip()}")

        status = "Success" if not stderr.strip() else "Warning"
        details = "Tomcat start command executed"
        if status != "Success":
            details = f"Tomcat start command completed with stderr: {stderr.strip()}"

        ready_output, ready_error, ready_ok = self._wait_for_ready_windows(
            executor,
            port,
            ready_timeout,
        )
        if ready_output.strip():
            logs.append(ready_output.strip())
        if ready_error.strip():
            logs.append(f"stderr: {ready_error.strip()}")

        if not ready_ok:
            return {
                "name": self.name,
                "status": "Failed",
                "command": command,
                "output": "\n".join(logs),
                "details": f"Timed out waiting for Tomcat port {port}",
                "tomcat_home": tomcat_home,
            }

        details = f"Tomcat started and port {port} is listening"
        if status != "Warning":
            status = "Success"

        return {
            "name": self.name,
            "status": status,
            "command": command,
            "output": "\n".join(logs),
            "details": details,
            "tomcat_home": tomcat_home,
        }

    # ------------------------------------------------------------------
    # Linux implementation
    # ------------------------------------------------------------------
    def _start_linux(
        self,
        executor: RemoteExecutor,
        tomcat_home: str,
        os_cfg: Dict[str, Any],
        cfg: Dict[str, Any],
        exec_timeout: float,
        ready_timeout: float,
        port: int,
        logs: List[str],
    ) -> Dict[str, Any]:
        command_template = os_cfg.get("start_command") or cfg.get("start_command")
        if not command_template:
            root = tomcat_home.rstrip("/")
            quoted_root = shlex.quote(root)
            # Execute startup.sh and wait a bit to verify it started
            script = (
                f"if [ ! -d {quoted_root} ]; then "
                f"echo 'Tomcat directory not found: {root}' >&2; exit 1; fi; "
                f"cd {quoted_root}/bin && "
                f"chmod +x startup.sh && "
                f"nohup ./startup.sh >/dev/null 2>&1 & "
                f"sleep 3; "
                f"if pgrep -f 'catalina|tomcat' >/dev/null; then "
                f"echo 'Tomcat process started'; else echo 'Warning: Tomcat process not detected yet' >&2; fi"
            )
            command = f"bash -lc {shlex.quote(script)}"
        else:
            command = command_template.format(tomcat_home=tomcat_home)

        logs.append(f"Executing start command: {command}")
        stdout, stderr = executor.run(command, timeout=exec_timeout)
        if stdout.strip():
            logs.append(stdout.strip())
        if stderr.strip():
            logs.append(f"stderr: {stderr.strip()}")

        status = "Success" if not stderr.strip() else "Warning"
        details = "Tomcat start command executed"
        if status != "Success":
            details = f"Tomcat start command completed with stderr: {stderr.strip()}"

        ready_output, ready_error, ready_ok = self._wait_for_ready_linux(
            executor,
            port,
            ready_timeout,
        )
        if ready_output.strip():
            logs.append(ready_output.strip())
        if ready_error.strip():
            logs.append(f"stderr: {ready_error.strip()}")

        if not ready_ok:
            return {
                "name": self.name,
                "status": "Failed",
                "command": command,
                "output": "\n".join(logs),
                "details": f"Timed out waiting for Tomcat port {port}",
                "tomcat_home": tomcat_home,
            }

        details = f"Tomcat started and port {port} is listening"
        if status != "Warning":
            status = "Success"

        return {
            "name": self.name,
            "status": status,
            "command": command,
            "output": "\n".join(logs),
            "details": details,
            "tomcat_home": tomcat_home,
        }

    def _wait_for_ready_windows(
        self,
        executor: RemoteExecutor,
        port: int,
        timeout: float,
    ) -> tuple[str, str, bool]:
        script = (
            f"$port = {port};"
            f"$deadline = (Get-Date).AddSeconds({int(timeout)});"
            "while ((Get-Date) -lt $deadline) {"
            "  $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners();"
            "  if ($listeners | Where-Object { $_.Port -eq $port }) {"
            "    Write-Output \"Port $port is listening.\"; exit 0"
            "  }"
            "  Start-Sleep -Milliseconds 500"
            "}"
            f"Write-Error \"Tomcat port {port} not listening after {int(timeout)}s\"; exit 1"
        )
        command = f"powershell -NoProfile -Command \"& {{ {script} }}\""

        try:
            stdout, stderr = executor.run(command, timeout=timeout + 5)
            success = not stderr.strip()
            return stdout, stderr, success
        except TimeoutError as exc:
            return "", str(exc), False

    def _wait_for_ready_linux(
        self,
        executor: RemoteExecutor,
        port: int,
        timeout: float,
    ) -> tuple[str, str, bool]:
        script = (
            f"end=$((SECONDS+{int(timeout)}));"
            "while [ $SECONDS -lt $end ]; do "
            f"if ss -ltn '( sport = :{port} )' 2>/dev/null | grep -q {port}; then "
            f"echo 'Port {port} is listening.'; exit 0; fi; "
            "sleep 0.5;"
            "done;"
            f"echo 'Tomcat port {port} not listening after {int(timeout)}s' 1>&2; exit 1"
        )
        command = f"bash -lc {shlex.quote(script)}"

        try:
            stdout, stderr = executor.run(command, timeout=timeout + 5)
            success = not stderr.strip()
            return stdout, stderr, success
        except TimeoutError as exc:
            return "", str(exc), False

    def _resolve_timeout(self, os_cfg: Dict[str, Any], cfg: Dict[str, Any]) -> float:
        candidates = [
            os_cfg.get("timeout") if isinstance(os_cfg, dict) else None,
            cfg.get("timeout") if isinstance(cfg, dict) else None,
        ]
        for value in candidates:
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return 120.0

    def _resolve_ready_timeout(self, os_cfg: Dict[str, Any], cfg: Dict[str, Any]) -> float:
        candidates = [
            os_cfg.get("ready_timeout") if isinstance(os_cfg, dict) else None,
            cfg.get("ready_timeout") if isinstance(cfg, dict) else None,
        ]
        for value in candidates:
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return 120.0

    def _resolve_port(self, os_cfg: Dict[str, Any], cfg: Dict[str, Any]) -> int:
        candidates = [
            os_cfg.get("port") if isinstance(os_cfg, dict) else None,
            cfg.get("port") if isinstance(cfg, dict) else None,
        ]
        for value in candidates:
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return 8080

    def _failure(self, message: str, logs: List[str]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": "remote_tomcat_start",
            "output": "\n".join(logs),
            "details": message,
        }
