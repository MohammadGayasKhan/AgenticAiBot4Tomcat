import os
from typing import Dict, Any

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor

try:
    from ..utilities.remote_download import RemoteCurlDownloadTool, _to_ps_literal
    from ..utilities.remote_extract import RemoteZipExtractTool
except ImportError:  # pragma: no cover
    from utilities.remote_download import RemoteCurlDownloadTool, _to_ps_literal  # type: ignore
    from utilities.remote_extract import RemoteZipExtractTool  # type: ignore


class RemoteTomcatInstallTool(RemoteTool):
    """Install Apache Tomcat on a remote host using configuration-driven settings."""

    config_path = ("install", "tomcat")

    def __init__(self) -> None:
        super().__init__(
            name="remote_tomcat_install",
            description="Download and install Apache Tomcat remotely (Windows/Linux)",
            parameters={},
            user_parameters={},
        )
        self._download_tool = RemoteCurlDownloadTool()
        self._extract_tool = RemoteZipExtractTool()

    def run(self, executor: RemoteExecutor, config: Dict[str, Any]) -> Dict[str, Any]:
        logs = []
        try:
            logs.append("Detecting remote operating system...")
            os_type = executor.detect_os()
            logs.append(f"✔ Detected OS: {os_type}")

            if os_type == "windows":
                return self._install_windows(executor, config.get("windows", {}), logs)
            if os_type == "linux":
                return self._install_linux(executor, config.get("linux", {}), logs)

            logs.append("Unsupported operating system detected")
            return self._failure("Unsupported OS", logs)

        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"Exception: {exc}")
            return self._failure(str(exc), logs)

    # ------------------------------------------------------------------
    # Windows install flow
    # ------------------------------------------------------------------
    def _install_windows(self, executor: RemoteExecutor, cfg: Dict[str, Any], logs) -> Dict[str, Any]:
        download_url = cfg.get("download_url")
        archive_path = cfg.get("archive_path")
        install_root = cfg.get("install_root")
        folder_pattern = cfg.get("folder_pattern", r"^apache-tomcat-")
        min_size = int(cfg.get("min_download_size", 100000))

        if not all([download_url, archive_path, install_root]):
            return self._missing_config("windows", logs)

        # Ensure directories
        self._ensure_directory(executor, os.path.dirname(archive_path))
        self._ensure_directory(executor, install_root)

        logs.append("Downloading Tomcat archive...")
        download_result = self._download_tool.run(
            executor=executor,
            url=download_url,
            destination=archive_path,
            min_size=min_size,
            extra_args=cfg.get("curl_extra_args"),
        )
        download_details = download_result.get("details", "").strip()
        if download_details:
            logs.append(download_details)
        if download_result.get("status") != "Success":
            return self._failure("Download failed", logs, download_result)

        logs.append("Extracting archive...")
        extract_target = install_root
        extract_result = self._extract_tool.run(
            executor=executor,
            source=archive_path,
            destination=extract_target,
            folder_pattern=folder_pattern,
        )
        extract_details = extract_result.get("details", "").strip()
        if extract_details:
            logs.append(extract_details)
        if extract_result.get("status") != "Success":
            return self._failure("Extraction failed", logs, extract_result)

        folder_name = extract_result.get("metadata", {}).get("folder_name", "")
        tomcat_dir = self._join_path(install_root, folder_name)
        if not tomcat_dir.strip():
            return self._failure("Unable to resolve Tomcat directory", logs)

        self._set_permissions_windows(executor, tomcat_dir, logs)

        if cfg.get("cleanup_archive", True):
            logs.append("Cleaning up archive...")
            archive_literal = _to_ps_literal(archive_path)
            executor.run(
                "powershell -Command \""
                f"$archive = {archive_literal};"
                "if (Test-Path $archive) { Remove-Item -Force $archive }"
                "\""
            )

        details = f"Tomcat extracted to {tomcat_dir}"
        return {
            "name": self.name,
            "status": "Success",
            "command": f"Install Tomcat -> {download_url}",
            "output": "\n".join(filter(None, logs)),
            "details": details,
            "tomcat_home": tomcat_dir,
        }

    def _set_permissions_windows(self, executor: RemoteExecutor, tomcat_dir: str, logs) -> None:
        bin_literal = _to_ps_literal(os.path.join(tomcat_dir, "bin"))
        command = (
            "powershell -Command \""
            f"$bin = {bin_literal};"
            "Get-ChildItem $bin -Filter '*.bat' | ForEach-Object { $_.Attributes='Normal' }"
            "\""
        )
        executor.run(command)
        logs.append("Set executable attributes for Windows scripts")

    # ------------------------------------------------------------------
    # Linux install flow
    # ------------------------------------------------------------------
    def _install_linux(self, executor: RemoteExecutor, cfg: Dict[str, Any], logs) -> Dict[str, Any]:
        download_url = cfg.get("download_url")
        archive_path = cfg.get("archive_path")
        install_root = cfg.get("install_root")

        if not all([download_url, archive_path, install_root]):
            return self._missing_config("linux", logs)

        strip_components = int(cfg.get("strip_components", 1))

        logs.append("Preparing directories...")
        executor.run(f"mkdir -p {install_root}")

        logs.append("Downloading Tomcat archive...")
        executor.run(f"wget -O {archive_path} {download_url}")

        logs.append("Extracting archive...")
        tar_cmd = "tar -xzf" if archive_path.endswith(".gz") else "tar -xf"
        executor.run(f"{tar_cmd} {archive_path} -C {install_root} --strip-components={strip_components}")

        if cfg.get("cleanup_archive", True):
            executor.run(f"rm -f {archive_path}")

        tomcat_dir = cfg.get("final_directory") or install_root
        logs.append("Adjusting permissions...")
        executor.run(f"chmod +x {tomcat_dir}/bin/*.sh")

        details = f"Tomcat extracted to {tomcat_dir}"
        return {
            "name": self.name,
            "status": "Success",
            "command": f"Install Tomcat -> {download_url}",
            "output": "\n".join(filter(None, logs)),
            "details": details,
            "tomcat_home": tomcat_dir,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _missing_config(self, section: str, logs) -> Dict[str, Any]:
        logs.append(f"Missing required configuration for {section}")
        return self._failure(f"Configuration missing for {section}", logs)

    def _failure(self, message: str, logs, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "status": "Failed",
            "command": "remote_tomcat_install",
            "output": "\n".join(filter(None, logs)),
            "details": message,
        }
        if payload:
            result["payload"] = payload
        return result

    def _ensure_directory(self, executor: RemoteExecutor, path: str) -> None:
        literal = _to_ps_literal(path)
        command = (
            "powershell -Command \""
            f"$path = {literal};"
            "if (!(Test-Path -Path $path)) {"
            "    New-Item -ItemType Directory -Force -Path $path | Out-Null"
            "}"
            "\""
        )
        executor.run(command)

    def _join_path(self, base: str, leaf: str) -> str:
        if not leaf:
            return base
        if base.endswith(("\\", "/")):
            return f"{base}{leaf}"
        separator = "\\" if "\\" in base else "/"
        return f"{base}{separator}{leaf}"
