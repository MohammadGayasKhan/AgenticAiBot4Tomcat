import configparser
import os
from typing import Any, Dict, Iterable, List

import yaml


def load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"YAML configuration not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_server_ini(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Server INI file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    defaults = {k: v for k, v in parser.items("defaults")} if parser.has_section("defaults") else {}

    servers: List[Dict[str, Any]] = []
    for section in parser.sections():
        if section.lower() == "defaults":
            continue
        data = defaults.copy()
        data.update({k: v for k, v in parser.items(section)})
        data.setdefault("name", section)
        required = ["host", "username"]
        missing = [field for field in required if not data.get(field)]
        if missing:
            raise ValueError(f"Section '{section}' missing required fields: {', '.join(missing)}")
        servers.append(data)

    return servers


def merge_dict(base: Dict[str, Any], overrides: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    result = base.copy()
    for layer in overrides:
        result = _deep_merge(result, layer)
    return result


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = base.copy()
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
