"""Manual test script for RemoteTomcatUninstallTool."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Remote.install.remote_tomcat_uninstall import RemoteTomcatUninstallTool
from Remote.remote_executor import RemoteExecutor
from Remote.utilities.config_loader import load_server_ini, load_yaml

DEFAULT_SETTINGS = os.path.join(ROOT, "Remote", "config", "settings.yaml")
DEFAULT_SERVERS = os.path.join(ROOT, "Remote", "config", "servers.ini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remote Tomcat uninstall test script")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="Path to settings.yaml")
    parser.add_argument("--servers", default=DEFAULT_SERVERS, help="Path to servers.ini")
    parser.add_argument("--server", help="Server key from servers.ini (defaults to first entry)")
    parser.add_argument("--tomcat-home", dest="tomcat_home", help="Tomcat install directory to remove")
    parser.add_argument(
        "--cleanup-logs",
        dest="cleanup_logs",
        type=_bool,
        default=None,
        help="Override cleanup_logs flag (true/false)",
    )
    return parser.parse_args()


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


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
    server_cfg = pick_server(servers, args.server)

    print(
        f"Running remote_tomcat_uninstall as {server_cfg.get('username')} on {server_cfg.get('host')}"
    )

    executor = RemoteExecutor(
        host=server_cfg["host"],
        username=server_cfg["username"],
        password=server_cfg.get("password") or None,
        key_path=server_cfg.get("key_path") or None,
    )
    executor.connect()
    try:
        tool = RemoteTomcatUninstallTool()
        config = settings.get(tool.config_path[0], {}).get(tool.config_path[1], {})
        result = tool.run(
            executor=executor,
            config=config,
            tomcat_home=args.tomcat_home,
            cleanup_logs=args.cleanup_logs,
        )
        print(json.dumps(result, indent=2))
    finally:
        executor.close()


if __name__ == "__main__":
    main()
