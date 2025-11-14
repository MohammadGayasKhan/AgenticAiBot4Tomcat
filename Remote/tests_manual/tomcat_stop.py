"""Manual test script for RemoteTomcatStopTool."""

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
from Remote.post_install import RemoteTomcatStopTool

DEFAULT_SETTINGS = os.path.join(ROOT, "Remote", "config", "settings.yaml")
DEFAULT_SERVERS = os.path.join(ROOT, "Remote", "config", "servers.ini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop Apache Tomcat remotely")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="Path to settings.yaml")
    parser.add_argument("--servers", default=DEFAULT_SERVERS, help="Path to servers.ini")
    parser.add_argument("--server", default=None, help="Server name/host from servers.ini (defaults to first entry)")
    parser.add_argument("--tomcat-home", default=None, help="Override Tomcat home directory")
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


def resolve_tomcat_home(post_install_cfg: Dict[str, Any], stop_cfg: Dict[str, Any], override: str | None) -> str:
    candidate = (
        override
        or post_install_cfg.get("default_tomcat_home")
        or stop_cfg.get("tomcat_home")
    )
    if not candidate:
        raise SystemExit("Tomcat home must be provided via --tomcat-home or post_install defaults")
    return candidate


def main() -> None:
    args = parse_args()
    settings = load_yaml(args.settings)
    servers = load_server_ini(args.servers)
    server = pick_server(servers, args.server)

    print(
        f"Running remote_tomcat_stop as {server.get('username')} on {server.get('host')}"
    )

    post_install_cfg = settings.get("post_install", {})
    stop_cfg = post_install_cfg.get("tomcat_stop", {})
    tomcat_home = resolve_tomcat_home(post_install_cfg, stop_cfg, args.tomcat_home)

    executor = RemoteExecutor(
        host=server["host"],
        username=server["username"],
        password=server.get("password") or None,
        key_path=server.get("key_path") or None,
    )
    executor.connect()
    try:
        tool = RemoteTomcatStopTool()
        result = tool.run(
            executor=executor,
            config=stop_cfg,
            tomcat_home=tomcat_home,
        )
        print(json.dumps(result, indent=2))
    finally:
        executor.close()


if __name__ == "__main__":
    main()
