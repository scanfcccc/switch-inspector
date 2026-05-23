import tomllib
from typing import Any, Dict
from dataclasses import dataclass, field

from engine.plugin_base import PluginManifest


@dataclass
class PluginConfig:
    manifest: PluginManifest
    raw_config: Dict[str, Any] = field(default_factory=dict)


def load_plugin_config(path: str) -> PluginManifest:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    plugin = data.get("plugin", {})
    deps = plugin.get("dependencies", {})
    config_schema = plugin.get("config", {})
    entry_point = plugin.get("entry_point", "")

    return PluginManifest(
        name=plugin["name"],
        version=plugin.get("version", "0.1.0"),
        author=plugin.get("author", "unknown"),
        description=plugin.get("description", ""),
        plugin_type=plugin.get("type", "unknown"),
        dependencies=list(deps.keys()) if isinstance(deps, dict) else (deps if isinstance(deps, list) else []),
        config_schema=config_schema,
        entry_point=entry_point,
    )
