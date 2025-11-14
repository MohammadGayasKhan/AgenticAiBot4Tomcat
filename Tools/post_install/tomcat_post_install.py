import os
import time
from typing import Dict, Any, Optional

import requests

from .tool_base import Tool
from Tools.Installation.tomcat_start import StartTomcat
from Tools.Installation.tomcat_stop import StopTomcat


class PostInstallTomcat(Tool):
    """Start Tomcat and verify that the default HTTP endpoint responds."""

    def __init__(self) -> None:
        super().__init__(
            name="post_install_tomcat",
            description=(
                "Start Apache Tomcat and validate that it is serving HTTP traffic. "
                 "Defaults assume Tomcat 10.1.34 installed under C:\\temp\\tomcat_test."
            ),
            parameters={
                "tomcat_home": {
                    "type": "str",
                    "description": "Absolute Tomcat installation dir. Default: C\\\\temp\\\\tomcat_test\\\\apache-tomcat-10.1.34"
                },
                "host": {
                    "type": "str",
                    "description": "Host name used for verification HTTP request. Default: localhost"
                },
                "port": {
                    "type": "int",
                    "description": "Port to probe for Tomcat HTTP service. Default: 8080"
                },
                "wait_seconds": {
                    "type": "int",
                    "description": "Maximum seconds to wait for Tomcat to respond. Default: 30"
                },
                "attempt_stop": {
                    "type": "bool",
                    "description": "When true, stop Tomcat after validation completes. Default: true"
                },
                "attempt_start": {
                    "type": "bool",
                    "description": "When true, run the Tomcat startup script before validating. Default: true"
                }
            }
        )

    def _check_installation(self, tomcat_home: str) -> None:
        if not os.path.isdir(tomcat_home):
            raise FileNotFoundError(f"Tomcat directory not found: {tomcat_home}")

        bin_dir = os.path.join(tomcat_home, "bin")
        if not os.path.isdir(bin_dir):
            raise FileNotFoundError(f"Tomcat bin directory missing: {bin_dir}")

    def _probe_http(self, host: str, port: int) -> Dict[str, Any]:
        url = f"http://{host}:{port}"
        try:
            response = requests.get(url, timeout=3)
            return {
                "running": response.ok,
                "status_code": response.status_code,
                "reason": response.reason,
                "error": "",
                "url": url,
            }
        except requests.RequestException as exc:
            return {
                "running": False,
                "status_code": None,
                "reason": "",
                "error": str(exc),
                "url": url,
            }

    def run(
        self,
        tomcat_home: str = r"C:\\temp\\tomcat_test\\apache-tomcat-10.1.34",
        host: str = "localhost",
        port: int = 8080,
        wait_seconds: int = 30,
        attempt_start: bool = True,
        attempt_stop: bool = True,
    ) -> Dict[str, Any]:
        try:
            self._check_installation(tomcat_home)
            logs_dir = os.path.join(tomcat_home, "logs")

            step_outputs = []
            start_result: Optional[Dict[str, Any]] = None
            stop_result: Optional[Dict[str, Any]] = None

            if attempt_start:
                starter = StartTomcat()
                start_result = starter.run(tomcat_home=tomcat_home)
                step_outputs.append(
                    f"StartTomcat status: {start_result.get('status')}\n{start_result.get('details', '')}\n{start_result.get('output', '')}"
                )

                if start_result.get("status") != "Success":
                    combined_output = "\n\n".join(step_outputs)
                    return {
                        "status": "Failed",
                        "command": f"post_install_tomcat -> start ({tomcat_home})",
                        "output": combined_output,
                        "details": "Tomcat startup failed; see output for details.",
                        "start_result": start_result,
                        "stop_result": stop_result,
                    }

            start_time = time.time()
            deadline = start_time + max(wait_seconds, 1)
            last_probe: Optional[Dict[str, Any]] = None

            while time.time() < deadline:
                last_probe = self._probe_http(host, port)
                if last_probe.get("running"):
                    break
                time.sleep(2)

            elapsed = max(0.0, time.time() - start_time)
            probe_summary = last_probe or {}
            step_outputs.append(
                "Verification: "
                + (
                    f"HTTP {probe_summary.get('status_code')} {probe_summary.get('reason')} at {probe_summary.get('url')}"
                    if probe_summary.get("running")
                    else f"No HTTP response from {probe_summary.get('url')}"
                )
            )

            if probe_summary.get("running"):
                if attempt_stop:
                    stopper = StopTomcat()
                    stop_result = stopper.run(tomcat_home=tomcat_home)
                    step_outputs.append(
                        f"StopTomcat status: {stop_result.get('status')}\n{stop_result.get('details', '')}\n{stop_result.get('output', '')}"
                    )

                output_text = (
                    "\n\n".join(step_outputs)
                    + f"\nTomcat responded after approximately {elapsed:.1f} seconds."
                )
                details = f"Tomcat is accepting HTTP requests on {host}:{port}."
                final_status = "Success"

                if attempt_stop and stop_result is not None:
                    stop_status = stop_result.get("status")
                    if stop_status == "Success":
                        details += " Tomcat was stopped after validation."
                    elif stop_status == "Not Running":
                        details += " Tomcat was already stopped after validation."
                    else:
                        final_status = "Failed"
                        details = "Validation succeeded, but stopping Tomcat failed."

                return {
                    "status": final_status,
                    "command": f"post_install_tomcat -> verify http://{host}:{port}",
                    "output": output_text.strip(),
                    "details": details,
                    "verification": probe_summary,
                    "start_result": start_result,
                    "stop_result": stop_result,
                }

            error_text = probe_summary.get("error", "Tomcat did not respond before timeout.")
            if attempt_stop and stop_result is None:
                stopper = StopTomcat()
                stop_result = stopper.run(tomcat_home=tomcat_home)
                step_outputs.append(
                    f"StopTomcat status: {stop_result.get('status')}\n{stop_result.get('details', '')}\n{stop_result.get('output', '')}"
                )

            output_lines = step_outputs + [
                f"Tomcat did not respond within {wait_seconds} seconds.",
                f"Last error: {error_text}",
                f"Check logs under: {logs_dir}",
            ]
            return {
                "status": "Failed",
                "command": f"post_install_tomcat -> verify http://{host}:{port}",
                "output": "\n".join(output_lines).strip(),
                "details": "Tomcat did not respond before timeout; see output for troubleshooting steps.",
                "verification": probe_summary,
                "start_result": start_result,
                "stop_result": stop_result,
            }

        except Exception as exc:
            return {
                "status": "Failed",
                "command": "post_install_tomcat",
                "output": str(exc),
                "details": f"Post-install validation failed: {exc}",
            }
