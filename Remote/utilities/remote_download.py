from typing import Dict, Any, Optional, TYPE_CHECKING

from Remote.tool_base import RemoteTool

if TYPE_CHECKING:  # pragma: no cover - only for typing
    from Remote.remote_executor import RemoteExecutor


def _to_ps_literal(path: str) -> str:
    """Return a PowerShell-friendly literal or expression for a remote path."""
    trimmed = path.strip()
    if not trimmed:
        return "''"
    if trimmed.startswith("$"):
        parts = [p for p in trimmed.split("\\") if p]
        if not parts:
            return trimmed
        expr = parts[0]
        for segment in parts[1:]:
            escaped_segment = segment.replace("'", "''")
            expr = f"(Join-Path {expr} '{escaped_segment}')"
        return expr
    escaped = trimmed.replace("'", "''")
    return f"'{escaped}'"


class RemoteCurlDownloadTool(RemoteTool):
    """Download a file on a remote host using curl.exe via PowerShell."""

    def __init__(self) -> None:
        super().__init__(
            name="remote_curl_download",
            description="Download remote artifacts using curl.exe",
            parameters={
                "executor": "RemoteExecutor instance",
                "url": "HTTPS/HTTP URL to download",
                "destination": "Remote path for downloaded file",
                "min_size": "Minimum expected size for validation",
            },
        )

    def run(
        self,
        executor: "RemoteExecutor",
        url: str,
        destination: str,
        min_size: int = 1024,
        extra_args: Optional[str] = None,
    ) -> Dict[str, Any]:
        logs = []
        try:
            dest_literal = _to_ps_literal(destination)
            args_segment = f" {extra_args.strip()}" if extra_args else ""
            url_literal = url.replace("'", "''")
            curl_cmd_parts = [
                "powershell -Command \"",
                f"$destination = {dest_literal};",
                f"$url = '{url_literal}';",
                f"curl.exe -L $url -o $destination{args_segment};",
                "\"",
            ]
            curl_cmd = "".join(curl_cmd_parts)
            out, err = executor.run(curl_cmd)
            if out.strip():
                logs.append(out.strip())
            if err.strip():
                logs.append(err.strip())

            size_cmd = (
                "powershell -Command \""
                f"$destination = {dest_literal};"
                "(Get-Item $destination -ErrorAction SilentlyContinue).Length"
                "\""
            )
            size_out, size_err = executor.run(size_cmd)
            if size_err.strip():
                logs.append(size_err.strip())
            size_value = size_out.strip()

            status = "Failed"
            if size_value.isdigit() and int(size_value) >= max(min_size, 0):
                status = "Success"
                logs.append(f"Download size verified: {size_value} bytes")
            else:
                logs.append(
                    f"Expected at least {max(min_size, 0)} bytes but got '{size_value}'."
                )

            return {
                "name": self.name,
                "status": status,
                "command": "curl.exe",
                "output": out + err,
                "details": "\n".join(logs),
                "metadata": {
                    "destination": destination,
                    "size": size_value,
                },
            }
        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return {
                "name": self.name,
                "status": "Failed",
                "command": "curl.exe",
                "output": "",
                "details": "\n".join(logs),
            }
