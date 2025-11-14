import shlex
from typing import Any, Dict, Optional

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor


class RemoteDiskCheckTool(RemoteTool):
    """Check available disk space on a remote Windows or Linux host."""

    config_path = ("pre_install", "disk_check")

    def __init__(self) -> None:
        super().__init__(
            name="remote_disk_check",
            description="Inspect free disk space on the remote host and validate against configured thresholds.",
            parameters={},
            user_parameters={
                "path": {
                    "type": "str",
                    "description": "Optional override for path/drive to inspect",
                },
                "min_free_mb": {
                    "type": "int",
                    "description": "Optional override for minimum free space threshold in MB",
                },
            },
        )

    def run(
        self,
        executor: RemoteExecutor,
        config: Dict[str, Any],
        path: Optional[str] = None,
        min_free_mb: Optional[int] = None,
    ) -> Dict[str, Any]:
        logs = []
        try:
            os_type = executor.detect_os()
            logs.append(f"Detected OS: {os_type}")

            os_cfg = config.get(os_type, {}) if isinstance(config, dict) else {}
            target_path = path or os_cfg.get("path")
            if not target_path:
                target_path = "C:\\" if os_type == "windows" else "/"

            threshold = min_free_mb if min_free_mb is not None else os_cfg.get("min_free_mb", 2048)
            threshold = int(threshold)

            if os_type == "windows":
                result = self._check_windows(executor, target_path, threshold, logs)
            elif os_type == "linux":
                result = self._check_linux(executor, target_path, threshold, logs)
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
        target_path: str,
        threshold: int,
        logs: Any,
    ) -> Dict[str, Any]:
        drive_letter = self._extract_drive(target_path)
        logs.append(f"Inspecting drive {drive_letter} on Windows host")
        command = (
            "powershell -NoProfile -Command \""
            f"$disk = Get-CimInstance Win32_LogicalDisk -Filter \\\"DeviceID='{drive_letter}'\\\";"
            "if ($disk) {"
            "  $totalMB = [math]::Round($disk.Size/1MB,2);"
            "  $freeMB = [math]::Round($disk.FreeSpace/1MB,2);"
            "  Write-Output (\\\"TOTAL=$totalMB;FREE=$freeMB\\\");"
            "} else { Write-Output 'ERROR:DiskNotFound'; }\""
        )
        stdout, stderr = executor.run(command)
        payload = (stdout + stderr).strip()
        logs.append(payload)

        if "ERROR" in payload.upper():
            return self._failure("Unable to retrieve disk details", logs)

        metrics = self._parse_metrics(payload)
        if not metrics:
            return self._failure("Unrecognized disk output", logs)

        status = "Success" if metrics["free_mb"] >= threshold else "Failed"
        details = (
            f"Free space {metrics['free_mb']:.2f} MB meets threshold {threshold} MB"
            if status == "Success"
            else f"Free space {metrics['free_mb']:.2f} MB below threshold {threshold} MB"
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
        target_path: str,
        threshold: int,
        logs: Any,
    ) -> Dict[str, Any]:
        logs.append(f"Inspecting path {target_path} on Linux host")
        quoted = shlex.quote(target_path)
        command = f"bash -lc \"df -Pm {quoted} | tail -1\""
        stdout, stderr = executor.run(command)
        logs.extend(filter(None, [stdout.strip(), stderr.strip()]))
        line = stdout.strip().splitlines()
        if not line:
            return self._failure("No output from df command", logs)

        parts = line[-1].split()
        if len(parts) < 4:
            return self._failure("Unexpected df output", logs)

        total_mb = float(parts[1])
        used_mb = float(parts[2])
        free_mb = float(parts[3])

        status = "Success" if free_mb >= threshold else "Failed"
        details = (
            f"Free space {free_mb:.2f} MB meets threshold {threshold} MB"
            if status == "Success"
            else f"Free space {free_mb:.2f} MB below threshold {threshold} MB"
        )

        return {
            "name": self.name,
            "status": status,
            "command": command,
            "details": details,
            "metrics": {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "free_mb": free_mb,
            },
        }

    def _extract_drive(self, path: str) -> str:
        candidate = path.strip().split(":", 1)[0]
        if candidate and candidate[0].isalpha():
            return f"{candidate[0].upper()}:"
        return "C:"

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
        if "total_mb" in metrics and "free_mb" in metrics:
            used = metrics["total_mb"] - metrics["free_mb"]
            metrics.setdefault("used_mb", used)
            return metrics
        return None

    def _failure(self, message: str, logs: Any) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "Failed",
            "command": self.name,
            "details": message,
            "output": "\n".join(str(item) for item in logs),
        }
