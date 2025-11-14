from typing import Any, Dict, Optional

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor


class RemoteRamCheckTool(RemoteTool):
    """Check total and available RAM on a remote Windows or Linux host."""

    config_path = ("pre_install", "ram_check")

    def __init__(self) -> None:
        super().__init__(
            name="remote_ram_check",
            description="Validate remote physical memory against configured thresholds.",
            parameters={},
            user_parameters={
                "min_mb": {
                    "type": "int",
                    "description": "Optional override for minimum RAM in MB",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        min_mb: Optional[int] = None,
    ) -> Dict[str, Any]:
        logs = []
        try:
            os_type = executor.detect_os()
            logs.append(f"Detected OS: {os_type}")

            os_cfg = config.get(os_type, {}) if isinstance(config, dict) else {}
            threshold = int(min_mb if min_mb is not None else os_cfg.get("min_mb", 2048))

            if os_type == "windows":
                result = self._check_windows(executor, threshold, logs)
            elif os_type == "linux":
                result = self._check_linux(executor, threshold, logs)
            else:
                return self._failure("Unsupported operating system", logs)

            result.setdefault("output", "\n".join(logs))
            return result

        except Exception as exc:  # pragma: no cover - defensive handling for remote execution
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    def _check_windows(
        self,
        executor: RemoteExecutor,
        threshold: int,
        logs: Any,
    ) -> Dict[str, Any]:
        command = (
            "powershell -NoProfile -Command \""
            "$cs = Get-CimInstance Win32_ComputerSystem;"
            "$os = Get-CimInstance Win32_OperatingSystem;"
            "$total = [math]::Round($cs.TotalPhysicalMemory/1MB,0);"
            "$free = [math]::Round($os.FreePhysicalMemory/1KB,0);"
            "Write-Output (\\\"TOTAL=$total;FREE=$free\\\");\""
        )
        stdout, stderr = executor.run(command)
        payload = (stdout + stderr).strip()
        logs.append(payload or "No output")
        metrics = self._parse_metrics(payload)
        if not metrics:
            return self._failure("Unable to parse memory details", logs)

        status = "Success" if metrics["total_mb"] >= threshold else "Failed"
        details = (
            f"Total RAM {metrics['total_mb']:.0f} MB meets threshold {threshold} MB"
            if status == "Success"
            else f"Total RAM {metrics['total_mb']:.0f} MB below threshold {threshold} MB"
        )

        return {
            "name": self.name,
            "status": status,
            "command": command,
            "details": details,
            "metrics": metrics,
        }

    def _check_linux(
        self,
        executor: RemoteExecutor,
        threshold: int,
        logs: Any,
    ) -> Dict[str, Any]:
        command = "bash -lc \"free -m\""
        stdout, stderr = executor.run(command)
        logs.extend(filter(None, [stdout.strip(), stderr.strip()]))
        metrics = self._parse_linux_free(stdout)
        if not metrics:
            return self._failure("Unable to parse free -m output", logs)

        status = "Success" if metrics["total_mb"] >= threshold else "Failed"
        details = (
            f"Total RAM {metrics['total_mb']:.0f} MB meets threshold {threshold} MB"
            if status == "Success"
            else f"Total RAM {metrics['total_mb']:.0f} MB below threshold {threshold} MB"
        )

        return {
            "name": self.name,
            "status": status,
            "command": command,
            "details": details,
            "metrics": metrics,
        }

    def _parse_metrics(self, payload: str) -> Optional[Dict[str, float]]:
        parts = payload.replace("\r", "").split(";")
        metrics: Dict[str, float] = {}
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            try:
                metrics[f"{key.lower()}_mb"] = float(value)
            except ValueError:
                continue
        return metrics if "total_mb" in metrics else None

    def _parse_linux_free(self, output: str) -> Optional[Dict[str, float]]:
        for line in output.splitlines():
            normalized = line.strip().lower()
            if normalized.startswith("mem:"):
                parts = line.split()
                if len(parts) >= 7:
                    try:
                        total_mb = float(parts[1])
                        free_mb = float(parts[6])
                    except ValueError:
                        return None
                    return {
                        "total_mb": total_mb,
                        "free_mb": free_mb,
                    }
        return None

    def _failure(self, message: str, logs: Any) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "details": message,
            "output": "\n".join(str(item) for item in logs),
        }
