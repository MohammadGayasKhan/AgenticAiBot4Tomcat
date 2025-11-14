"""Validate Tomcat availability over HTTP."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from Remote.remote_executor import RemoteExecutor
from Remote.tool_base import RemoteTool


class RemoteTomcatValidationTool(RemoteTool):
    """Verify that a remote Tomcat instance responds over HTTP."""

    config_path = ("post_install", "tomcat_validation")

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_validation",
            description="Validate remote Tomcat by polling its HTTP endpoint",
            parameters={},
            user_parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Tomcat home directory (optional, used for metadata only)",
                },
                "port": {
                    "type": "int",
                    "description": "Override HTTP port checked for readiness",
                },
                "host_template": {
                    "type": "str",
                    "description": "Override the HTTP host template (defaults to {host})",
                },
                "wait_seconds": {
                    "type": "int",
                    "description": "Override wait time for HTTP readiness",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        server: Dict[str, Any],
        tomcat_home: str | None = None,
    ) -> Dict[str, Any]:
        del executor  # Validation uses only network checks against HTTP endpoint
        logs: List[str] = []
        try:
            wait_seconds = int(config.get("wait_seconds", 30))
            host_template = config.get("host_template", "{host}")
            port = int(config.get("port", 8080))

            http_host = host_template.format(**server)
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
                "url": url,
                "status_code": status_code,
            }
            if tomcat_home:
                payload["tomcat_home"] = tomcat_home
            return payload

        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    def _failure(self, message: str, logs: List[str]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": "remote_tomcat_validation",
            "output": "\n".join(filter(None, logs)),
            "details": message,
        }
