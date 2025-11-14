import re
from typing import Any, Dict, Iterable, List, Optional

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor


class RemotePortCheckTool(RemoteTool):
    """Inspect remote ports to determine if they are currently in use."""

    config_path = ("pre_install", "port_check")

    def __init__(self) -> None:
        super().__init__(
            name="remote_port_check",
            description="Check whether specified ports are occupied on the remote host (Windows/Linux).",
            parameters={},
            user_parameters={
                "ports": {
                    "type": "list[int] | str",
                    "description": "Optional override list of ports to inspect (list or comma separated)",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        ports: Optional[Iterable[int]] = None,
    ) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            os_type = executor.detect_os()
            logs.append(f"Detected OS: {os_type}")

            os_cfg = config.get(os_type, {}) if isinstance(config, dict) else {}
            port_values = ports if ports is not None else os_cfg.get("ports", [8080, 8005, 8009])
            port_list = self._normalize_ports(port_values)
            if not port_list:
                return self._failure("No valid ports supplied for inspection", logs)

            if os_type == "windows":
                return self._check_windows(executor, port_list, logs)
            if os_type == "linux":
                return self._check_linux(executor, port_list, logs)
            return self._failure("Unsupported operating system", logs)

        except Exception as exc:  # pragma: no cover - defensive handling for remote execution
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    def _check_windows(
        self,
        executor: RemoteExecutor,
        ports: List[int],
        logs: List[str],
    ) -> Dict[str, Any]:
        summary: List[str] = []
        stdout, stderr = executor.run("netstat -ano")
        raw_lines = (stdout + "\n" + stderr).splitlines()

        for port in ports:
            matches = [line for line in raw_lines if self._contains_port(line, port)]
            if not matches:
                summary.append(f"Port {port}: free")
                continue

            summary.append(f"Port {port}: IN USE")
            for line in matches:
                summary.append(f"  {line.strip()}")
                pid = self._extract_pid(line)
                if pid:
                    task_cmd = f'tasklist /FI "PID eq {pid}"'
                    task_out, task_err = executor.run(task_cmd)
                    task_lines = (task_out + "\n" + task_err).strip()
                    if task_lines:
                        summary.append(f"    {task_lines}")

        status = "Success" if all("free" in s.lower() for s in summary if s.startswith("Port")) else "Failed"
        logs.extend(summary)
        return {
            "name": self.name,
            "status": status,
            "command": "netstat -ano",
            "details": "\n".join(summary),
            "output": "\n".join(logs),
        }

    def _check_linux(
        self,
        executor: RemoteExecutor,
        ports: List[int],
        logs: List[str],
    ) -> Dict[str, Any]:
        summary: List[str] = []
        stdout, stderr = executor.run('bash -lc "ss -ltnp"')
        content = (stdout + "\n" + stderr).strip()
        if not content:
            stdout, stderr = executor.run('bash -lc "netstat -tulpn"')
            content = (stdout + "\n" + stderr).strip()
        lines = content.splitlines()

        for port in ports:
            matches = [line for line in lines if self._contains_port(line, port)]
            if not matches:
                summary.append(f"Port {port}: free")
                continue

            summary.append(f"Port {port}: IN USE")
            for line in matches:
                summary.append(f"  {line.strip()}")
                pid = self._extract_pid(line)
                if pid:
                    proc_cmd = f"bash -lc \"ps -p {pid} -o pid,cmd --no-headers\""
                    proc_out, proc_err = executor.run(proc_cmd)
                    proc_info = (proc_out + "\n" + proc_err).strip()
                    if proc_info:
                        summary.append(f"    {proc_info}")

        status = "Success" if all("free" in s.lower() for s in summary if s.startswith("Port")) else "Failed"
        logs.extend(summary)
        return {
            "name": self.name,
            "status": status,
            "command": "ss -ltnp | netstat -tulpn",
            "details": "\n".join(summary),
            "output": "\n".join(logs),
        }

    def _contains_port(self, line: str, port: int) -> bool:
        pattern = rf":{port}(?:\s|$)"
        return re.search(pattern, line) is not None

    def _extract_pid(self, line: str) -> Optional[str]:
        pid_match = re.search(r"pid=(\d+)", line)
        if pid_match:
            return pid_match.group(1)
        parts = line.split()
        if parts and parts[-1].isdigit():
            return parts[-1]
        return None

    def _normalize_ports(self, ports: Iterable[Any]) -> List[int]:
        normalized: List[int] = []
        for item in ports:
            if isinstance(item, str):
                try:
                    normalized.append(int(item.strip()))
                except ValueError:
                    continue
            else:
                try:
                    normalized.append(int(item))
                except (TypeError, ValueError):
                    continue
        return sorted(set(normalized))

    def _failure(self, message: str, logs: List[str]) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "details": message,
            "output": "\n".join(logs),
        }
