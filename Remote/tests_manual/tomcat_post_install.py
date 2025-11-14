"""Manual test script for Tomcat start, validation, and stop actions."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Remote.utilities.config_loader import load_server_ini, load_yaml
from Remote.remote_executor import RemoteExecutor
from Remote.post_install import (
    RemoteTomcatStartTool,
    RemoteTomcatValidationTool,
    RemoteTomcatStopTool,
)

DEFAULT_SETTINGS = os.path.join(ROOT, "Remote", "config", "settings.yaml")
DEFAULT_SERVERS = os.path.join(ROOT, "Remote", "config", "servers.ini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tomcat post-install stages remotely")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="Path to settings.yaml")
    parser.add_argument("--servers", default=DEFAULT_SERVERS, help="Path to servers.ini")
    parser.add_argument("--server", default=None, help="Server name/host from servers.ini (defaults to first entry)")
    parser.add_argument("--tomcat-home", default=None, help="Override Tomcat home directory")
    parser.add_argument("--skip-start", action="store_true", help="Skip running the start command")
    parser.add_argument("--skip-stop", action="store_true", help="Skip running the stop command")
    parser.add_argument("--wait-seconds", type=int, default=None, help="Override wait_seconds before HTTP timeout")
    parser.add_argument("--port", type=int, default=None, help="Override HTTP port")
    parser.add_argument("--host-template", default=None, help="Override host template (defaults to {host})")
    return parser.parse_args()


def pick_server(records, identifier):
    if not records:
        raise SystemExit("No servers defined in inventory")
    if identifier is None:
        return records[0]
    ident = identifier.strip().lower()
    for record in records:
        if ident in {str(record.get("name", "")).lower(), str(record.get("host", "")).lower()}:
            return record
    raise SystemExit(f"Server '{identifier}' not found in inventory")


def main() -> None:
    args = parse_args()
    settings = load_yaml(args.settings)
    servers = load_server_ini(args.servers)
    server = pick_server(servers, args.server)

    print(
        f"Running Tomcat post-install stages as {server.get('username')} on {server.get('host')}"
    )

    post_install = settings.get("post_install", {})
    start_cfg = post_install.get("tomcat_start", {})
    validation_cfg = post_install.get("tomcat_validation", {})
    stop_cfg = post_install.get("tomcat_stop", {})
    default_home = post_install.get("default_tomcat_home")

    tomcat_home = (
        args.tomcat_home
        or default_home
        or start_cfg.get("tomcat_home")
        or validation_cfg.get("tomcat_home")
        or stop_cfg.get("tomcat_home")
    )
    if not tomcat_home:
        raise SystemExit("Tomcat home must be provided via --tomcat-home or post_install defaults")

    if args.port is not None:
        validation_cfg = {**validation_cfg, "port": args.port}
    if args.wait_seconds is not None:
        validation_cfg = {**validation_cfg, "wait_seconds": args.wait_seconds}
    if args.host_template is not None:
        validation_cfg = {**validation_cfg, "host_template": args.host_template}

    executor = RemoteExecutor(
        host=server["host"],
        username=server["username"],
        password=server.get("password") or None,
        key_path=server.get("key_path") or None,
    )
    executor.connect()
    try:
        results: Dict[str, Any] = {}
        if not args.skip_start and start_cfg:
            start_tool = RemoteTomcatStartTool()
            results["start"] = start_tool.run(
                executor=executor,
                config=start_cfg,
                tomcat_home=tomcat_home,
            )

        validation_tool = RemoteTomcatValidationTool()
        results["validation"] = validation_tool.run(
            executor=executor,
            config=validation_cfg,
            server=server,
            tomcat_home=tomcat_home,
        )

        if not args.skip_stop and stop_cfg:
            stop_tool = RemoteTomcatStopTool()
            results["stop"] = stop_tool.run(
                executor=executor,
                config=stop_cfg,
                tomcat_home=tomcat_home,
            )

        print(json.dumps(results, indent=2))
    finally:
        executor.close()


if __name__ == "__main__":
    main()
