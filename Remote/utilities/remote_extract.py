from typing import Dict, Any, Optional, TYPE_CHECKING

from Remote.tool_base import RemoteTool

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from Remote.remote_executor import RemoteExecutor

try:
    from .remote_download import _to_ps_literal
except ImportError:  # pragma: no cover - top-level script fallback
    from remote_download import _to_ps_literal  # type: ignore


class RemoteZipExtractTool(RemoteTool):
    """Extract ZIP archives remotely and optionally resolve the top-level folder."""

    def __init__(self) -> None:
        super().__init__(
            name="remote_zip_extract",
            description="Expand ZIP files remotely via PowerShell",
            parameters={
                "executor": "RemoteExecutor instance",
                "source": "Zip archive to extract",
                "destination": "Destination directory on remote host",
                "folder_pattern": "Optional regex to detect extracted folder",
            },
        )

    def run(
        self,
        executor: "RemoteExecutor",
        source: str,
        destination: str,
        folder_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        logs = []
        try:
            source_literal = _to_ps_literal(source)
            destination_literal = _to_ps_literal(destination)

            expand_cmd = (
                "powershell -Command \""
                f"$source = {source_literal};"
                f"$destination = {destination_literal};"
                "Expand-Archive -LiteralPath $source -DestinationPath $destination -Force"
                "\""
            )
            out, err = executor.run(expand_cmd)
            if out.strip():
                logs.append(out.strip())
            error_text = err.strip()
            if error_text:
                logs.append(error_text)

            folder_name = ""
            if folder_pattern is not None:
                pattern_literal = folder_pattern.replace("'", "''")
                detect_cmd = (
                    "powershell -Command \""
                    f"$destination = {destination_literal};"
                    f"$pattern = '{pattern_literal}';"
                    "$dirs = Get-ChildItem -Path $destination -Directory;"
                    "if ($pattern) { $dirs = $dirs | Where-Object { $_.Name -match $pattern }; }"
                    "$match = $dirs | Sort-Object LastWriteTime -Descending | Select-Object -First 1;"
                    "if ($match) { $match.Name }"
                    "\""
                )
                folder_out, folder_err = executor.run(detect_cmd)
                if folder_err.strip():
                    logs.append(folder_err.strip())
                folder_name = folder_out.strip()
                if folder_name:
                    logs.append(f"Detected extracted folder: {folder_name}")
                else:
                    logs.append("No folder matched the supplied pattern.")

            status = "Success"
            if error_text:
                status = "Failed"
            if folder_pattern is not None and not folder_name:
                status = "Failed"
            return {
                "name": self.name,
                "status": status,
                "command": "Expand-Archive",
                "output": out + err,
                "details": "\n".join(logs),
                "metadata": {
                    "destination": destination,
                    "folder_name": folder_name,
                },
            }
        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return {
                "name": self.name,
                "status": "Failed",
                "command": "Expand-Archive",
                "output": "",
                "details": "\n".join(logs),
            }
