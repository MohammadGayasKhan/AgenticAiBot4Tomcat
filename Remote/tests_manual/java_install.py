"""Manual test script for RemoteJavaInstallTool."""

from __future__ import annotations

import argparse
import json

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Remote.utilities.config_loader import load_server_ini, load_yaml
from Remote.remote_executor import RemoteExecutor
from Remote.pre_install.remote_java_install import RemoteJavaInstallTool

DEFAULT_SETTINGS = os.path.join(ROOT, "Remote", "config", "settings.yaml")
DEFAULT_SERVERS = os.path.join(ROOT, "Remote", "config", "servers.ini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Java remotely")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="Path to settings.yaml")
    parser.add_argument("--servers", default=DEFAULT_SERVERS, help="Path to servers.ini")
    parser.add_argument(
        "--server",
        default=None,
        help="Server name/host from servers.ini (defaults to first entry)",
    )
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
        f"Running remote_java_install as {server.get('username')} on {server.get('host')}"
    )

    executor = RemoteExecutor(
        host=server["host"],
        username=server["username"],
        password=server.get("password") or None,
        key_path=server.get("key_path") or None,
    )
    executor.connect()
    try:
        tool = RemoteJavaInstallTool()
        config = settings.get("pre_install", {}).get("java", {})
        result = tool.run(executor=executor, config=config)
        print(json.dumps(result, indent=2))
    finally:
        executor.close()


if __name__ == "__main__":
    main()
