import argparse
from typing import Any, Dict, Optional

from Remote.remote_executor import RemoteExecutor
from Remote.utilities.config_loader import load_server_ini, load_yaml
from Remote.pre_install.remote_java_install import RemoteJavaInstallTool
from Remote.install.remote_tomcat_install import RemoteTomcatInstallTool
from Remote.post_install import (
    RemoteTomcatStartTool,
    RemoteTomcatStopTool,
    RemoteTomcatValidationTool,
)


class RemoteWorkflowRunner:
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.java_tool = RemoteJavaInstallTool()
        self.tomcat_install_tool = RemoteTomcatInstallTool()
        self.tomcat_start_tool = RemoteTomcatStartTool()
        self.tomcat_validation_tool = RemoteTomcatValidationTool()
        self.tomcat_stop_tool = RemoteTomcatStopTool()

    def run_for_server(self, server: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {"server": server.get("name", server.get("host"))}
        executor: Optional[RemoteExecutor] = None

        try:
            executor = RemoteExecutor(
                host=server["host"],
                username=server["username"],
                password=server.get("password") or None,
                key_path=server.get("key_path") or None,
            )
            try:
                executor.connect()
            except Exception as exc:  # pragma: no cover - network dependent
                results["connection"] = {
                    "status": "Failed",
                    "details": f"Unable to connect: {exc}",
                }
                return results

            # Pre-install: Java
            java_cfg = self.settings.get("pre_install", {}).get("java")
            if java_cfg:
                java_result = self.java_tool.run(executor, java_cfg)
                results["pre_install_java"] = java_result
                if java_result.get("status") != "Success":
                    return results

            # Install: Tomcat
            install_cfg = self.settings.get("install", {}).get("tomcat")
            tomcat_home = None
            if install_cfg:
                install_result = self.tomcat_install_tool.run(executor, install_cfg)
                results["install_tomcat"] = install_result
                if install_result.get("status") != "Success":
                    return results
                tomcat_home = install_result.get("tomcat_home")

            # Post-install
            post_cfg = self.settings.get("post_install", {})
            start_cfg = post_cfg.get("tomcat_start")
            validation_cfg = post_cfg.get("tomcat_validation")
            stop_cfg = post_cfg.get("tomcat_stop")

            default_home = post_cfg.get("default_tomcat_home") if isinstance(post_cfg, dict) else None
            effective_home = (
                tomcat_home
                or default_home
                or (start_cfg or {}).get("tomcat_home")
                or (validation_cfg or {}).get("tomcat_home")
                or (stop_cfg or {}).get("tomcat_home")
            )

            if start_cfg:
                start_result = self.tomcat_start_tool.run(
                    executor=executor,
                    config=start_cfg,
                    tomcat_home=effective_home,
                )
                results["post_install_tomcat_start"] = start_result

            if validation_cfg:
                if effective_home:
                    validation_result = self.tomcat_validation_tool.run(
                        executor=executor,
                        config=validation_cfg,
                        server=server,
                        tomcat_home=effective_home,
                    )
                    results["post_install_tomcat_validation"] = validation_result
                else:
                    results["post_install_tomcat_validation"] = {
                        "status": "Skipped",
                        "details": "Tomcat home not available for validation",
                    }

            if stop_cfg:
                stop_result = self.tomcat_stop_tool.run(
                    executor=executor,
                    config=stop_cfg,
                    tomcat_home=effective_home,
                )
                results["post_install_tomcat_stop"] = stop_result

            return results

        finally:
            if executor:
                executor.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run remote Tomcat workflow on multiple servers")
    parser.add_argument(
        "--settings",
        default="Remote/config/settings.yaml",
        help="Path to YAML settings file",
    )
    parser.add_argument(
        "--servers",
        default="Remote/config/servers.ini",
        help="Path to server inventory INI file",
    )
    args = parser.parse_args()

    settings = load_yaml(args.settings)
    servers = load_server_ini(args.servers)

    runner = RemoteWorkflowRunner(settings)

    for server in servers:
        result = runner.run_for_server(server)
        server_name = server.get("name", server.get("host"))
        print(f"=== Results for {server_name} ===")
        for key, value in result.items():
            if key == "server":
                continue
            if isinstance(value, dict):
                status = value.get("status", "n/a")
                details = value.get("details")
                print(f" - {key}: {status}")
                if details:
                    print(f"   details: {details}")
            else:
                print(f" - {key}: {value}")
        print()


if __name__ == "__main__":
    main()
