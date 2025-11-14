from typing import Dict, Any

from Remote.tool_base import RemoteTool
from Remote.remote_executor import RemoteExecutor

try:  # Prefer package-relative imports when available
    from ..utilities.remote_download import RemoteCurlDownloadTool
    from ..utilities.remote_extract import RemoteZipExtractTool
    from ..utilities.remote_download import _to_ps_literal
except ImportError:  # Fallback for script executions where pre_install is top-level
    from utilities.remote_download import RemoteCurlDownloadTool
    from utilities.remote_extract import RemoteZipExtractTool
    from utilities.remote_download import _to_ps_literal


class RemoteJavaInstallTool(RemoteTool):

    config_path = ("pre_install", "java")

    def __init__(self) -> None:
        super().__init__(
            name="remote_java_install",
            description="Install Java on remote Windows/Linux hosts using configuration-driven settings",
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

            # ============================================================
            #  LINUX PATH (unchanged)
            # ============================================================

            if os_type == "linux":
                linux_cfg = config.get("linux", {})
                download_url = linux_cfg.get("download_url")
                archive_path = linux_cfg.get("archive_path", "~/jdk.tar.gz")
                install_dir = linux_cfg.get("install_dir", "~/java")
                version_check = linux_cfg.get("version_check", "bash -lc '$HOME/java/*/bin/java -version'")
                packages = linux_cfg.get("packages", ["wget", "tar"])

                if not download_url:
                    return self._missing_config("linux.download_url", logs)

                logs.append("Checking existing Java...")
                out, err = executor.run("java -version")
                if "version" in (out + err).lower():
                    logs.append("✔ Java already installed.")
                    return {"name": self.name, "status": "Success", "command": "java -version", "output": out + err, "details": "\n".join(logs)}

                logs.append("Installing Java on Linux...")
                if packages:
                    pkg_cmd = linux_cfg.get("package_install_command", "sudo apt install -y {packages}")
                    pkg_list = " ".join(packages)
                    executor.run(linux_cfg.get("package_update_command", "sudo apt update -y"))
                    executor.run(pkg_cmd.format(packages=pkg_list))

                executor.run(f"wget -O {archive_path} {download_url}")
                executor.run(f"mkdir -p {install_dir}")
                executor.run(f"tar -xvf {archive_path} -C {install_dir}")
                out, err = executor.run(version_check)

                return {
                    "name": self.name,
                    "status": "Success" if "version" in (out + err).lower() else "Failed",
                    "command": "java -version",
                    "output": out + err,
                    "details": "\n".join(logs),
                }

            # ============================================================
            #  WINDOWS PATH (FIXED VERSION USING CURL.EXE)
            # ============================================================

            if os_type == "windows":
                win_cfg = config.get("windows", {})
                jdk_url = win_cfg.get("download_url")
                archive_path = win_cfg.get("archive_path")
                install_root = win_cfg.get("install_root")
                folder_pattern = win_cfg.get("folder_pattern", r"^(jdk|microsoft-jdk|msopenjdk)-")
                min_size = int(win_cfg.get("min_download_size", 50000))
                env_scopes = win_cfg.get("set_environment", True)

                if not all([jdk_url, archive_path, install_root]):
                    return self._missing_config("windows.(download_url/archive_path/install_root)", logs)

                logs.append("Checking existing Java...")
                out, err = executor.run('powershell -Command "java -version"')
                if "version" in (out + err).lower():
                    logs.append("✔ Java already installed.")
                    return {"name": self.name, "status": "Success", "command": "java -version", "output": out + err, "details": "\n".join(logs)}

                logs.append("Java not found → Installing Java...")

                # Create folders
                logs.append("Ensuring folders exist...")
                archive_dir = win_cfg.get("archive_dir") or archive_path.rsplit("\\", 1)[0]
                self._ensure_directory(executor, archive_dir)
                self._ensure_directory(executor, install_root)

                # -----------------------------
                # CURL DOWNLOAD (works!)
                # -----------------------------
                logs.append("Downloading JDK archive...")
                download_result = self._download_tool.run(
                    executor=executor,
                    url=jdk_url,
                    destination=archive_path,
                    min_size=min_size,
                    extra_args=win_cfg.get("curl_extra_args"),
                )
                download_details = download_result.get("details", "")
                if download_details:
                    logs.extend(download_details.splitlines())

                if download_result.get("status") != "Success":
                    download_result["details"] = "\n".join(logs)
                    download_result["name"] = self.name
                    download_result.setdefault("command", "curl.exe")
                    download_result.setdefault("output", "")
                    return download_result

                logs.append("✔ JDK download successful.")

                # -----------------------------
                # Extract ZIP
                # -----------------------------
                logs.append("Extracting JDK archive...")
                extract_result = self._extract_tool.run(
                    executor=executor,
                    source=archive_path,
                    destination=install_root,
                    folder_pattern=folder_pattern,
                )
                extract_details = extract_result.get("details", "")
                if extract_details:
                    logs.extend(extract_details.splitlines())

                jdk_folder = extract_result.get("metadata", {}).get("folder_name", "")
                if extract_result.get("status") != "Success" or not jdk_folder:
                    extract_result["details"] = "\n".join(logs)
                    extract_result["name"] = self.name
                    extract_result.setdefault("command", "Expand-Archive")
                    extract_result.setdefault("output", "")
                    return extract_result

                logs.append(f"✔ Extraction complete. Folder: {jdk_folder}")



                # -----------------------------
                # Set JAVA_HOME & PATH
                # -----------------------------
                java_home_expr = win_cfg.get("java_home_expression")
                if java_home_expr:
                    java_home_expr = java_home_expr.format(folder=jdk_folder)
                else:
                    java_home_expr = f"(Join-Path '{install_root}' '{jdk_folder}')"

                if env_scopes:
                    logs.append("Setting JAVA_HOME and PATH...")
                    env_scope = win_cfg.get("environment_scope", "User")
                    set_env_cmd = (
                        "powershell -Command \""
                        f"$javaHome = {java_home_expr};"
                        f"[Environment]::SetEnvironmentVariable('JAVA_HOME', $javaHome, '{env_scope}')"
                        "\""
                    )
                    _, err = executor.run(set_env_cmd)
                    if err.strip():
                        logs.append(err.strip())

                    path_cmd = (
                        "powershell -Command \""
                        f"$bin = Join-Path ({java_home_expr}) 'bin';"
                        f"$old=[Environment]::GetEnvironmentVariable('PATH','{env_scope}');"
                        "if ($old -notlike '*'+$bin+'*') {"
                        f"    [Environment]::SetEnvironmentVariable('PATH',$bin+';'+$old,'{env_scope}');"
                        "}"
                        "\""
                    )
                    _, err = executor.run(path_cmd)
                    if err.strip():
                        logs.append(err.strip())

                # -----------------------------
                # Test Java
                # -----------------------------
                logs.append("Testing Java installation...")
                default_version_cmd = f"powershell -Command \"& (Join-Path ({java_home_expr}) 'bin\\java.exe') -version\""
                version_command = win_cfg.get("version_command", default_version_cmd)
                version_command = version_command.format(folder=jdk_folder)
                out, err = executor.run(version_command)
                logs.append(out + err)

                return {
                    "name": self.name,
                    "status": "Success" if "version" in (out + err).lower() else "Failed",
                    "command": "java -version",
                    "output": out + err,
                    "details": "\n".join(logs)
                }

            return {"name": self.name, "status": "Failed", "details": "Unknown OS"}

        except Exception as e:
            logs.append("Exception: " + str(e))
            return {"name": self.name, "status": "Failed", "details": "\n".join(logs)}

    def _missing_config(self, path: str, logs) -> Dict[str, Any]:
        logs.append(f"Missing required configuration: {path}")
        return {
            "name": self.name,
            "status": "Failed",
            "command": "remote_java_install",
            "output": "",
            "details": "\n".join(logs),
        }

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
