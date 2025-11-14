import time
from typing import Any, Dict, Optional

import requests

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor


class RemoteTomcatPostInstallTool(RemoteTool):
    """Start Tomcat remotely, verify HTTP availability, and optionally shut it down."""

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_post_install",
            description="Validate remote Tomcat by starting, probing HTTP, and optionally stopping",
            parameters={
                "executor": "Connected RemoteExecutor instance",
                "config": "Dictionary extracted from YAML under post_install.tomcat",
                "server": "Server metadata dictionary (from INI)",
                "tomcat_home": "Resolved Tomcat home directory on target",
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        server: Dict[str, Any],
        tomcat_home: str,
    ) -> Dict[str, Any]:
        logs = []
        try:
            logs.append("Detecting remote operating system...")
            os_type = executor.detect_os()
            logs.append(f"✔ Detected OS: {os_type}")

            os_cfg = config.get(os_type, {})
            start_cmd_template = os_cfg.get("start_command")
            stop_cmd_template = os_cfg.get("stop_command")
            if config.get("attempt_start", True) and not start_cmd_template:
                return self._failure("start_command not configured", logs)
            if config.get("attempt_stop", True) and not stop_cmd_template:
                return self._failure("stop_command not configured", logs)

            start_result = None
            stop_result = None

            if config.get("attempt_start", True):
                start_command = start_cmd_template.format(tomcat_home=tomcat_home)
                logs.append(f"Starting Tomcat using: {start_command}")
                stdout, stderr = executor.run(start_command)
                start_result = {"stdout": stdout, "stderr": stderr}
                logs.append("Start command dispatched")

            wait_seconds = int(config.get("wait_seconds", 30))
            host_template = config.get("host_template", "{host}")
            http_host = host_template.format(**server)
            port = int(config.get("port", 8080))
            url = f"http://{http_host}:{port}"

            logs.append(f"Waiting up to {wait_seconds}s for HTTP {url}")
            deadline = time.time() + max(wait_seconds, 1)
            last_error: Optional[str] = None
            status_code: Optional[int] = None

            while time.time() < deadline:
                try:
                    response = requests.get(url, timeout=3)
                    status_code = response.status_code
                    if response.ok:
                        logs.append(f"Received HTTP {response.status_code}")
                        break
                    last_error = f"HTTP {response.status_code} {response.reason}"
                except requests.RequestException as exc:
                    last_error = str(exc)
                time.sleep(2)
            else:
                logs.append("Timed out waiting for HTTP response")

            running = status_code is not None and 200 <= status_code < 500

            if config.get("attempt_stop", True):
                stop_command = stop_cmd_template.format(tomcat_home=tomcat_home)
                logs.append(f"Stopping Tomcat using: {stop_command}")
                stdout, stderr = executor.run(stop_command)
                stop_result = {"stdout": stdout, "stderr": stderr}
                logs.append("Stop command dispatched")

            result_status = "Success" if running else "Failed"
            details = (
                f"Tomcat responded at {url} with HTTP {status_code}"
                if running
                else f"Tomcat did not respond at {url}: {last_error or 'unknown error'}"
            )

            payload: Dict[str, Any] = {
                "name": self.name,
                "status": result_status,
                "command": f"Validate Tomcat at {url}",
                "output": "\n".join(filter(None, logs)),
                "details": details,
                "start_result": start_result,
                "stop_result": stop_result,
                "url": url,
                "status_code": status_code,
            }
            return payload

        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    def _failure(self, message: str, logs) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": "remote_tomcat_post_install",
            "output": "\n".join(filter(None, logs)),
            "details": message,
        }
