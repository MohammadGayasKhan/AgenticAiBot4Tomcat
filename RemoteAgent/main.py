"""Deprecated entry point retained for backward compatibility."""

from __future__ import annotations


def main() -> None:  # pragma: no cover - simple compatibility shim
    raise SystemExit(
        "RemoteAgent.main is no longer available. Use 'python -m RemoteAgent.main_langchain' instead."
    )


if __name__ == "__main__":
    main()
