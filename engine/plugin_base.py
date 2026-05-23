from dataclasses import dataclass, field
from typing import List, Dict, ClassVar
from abc import ABC, abstractmethod


@dataclass
class PluginManifest:
    name: str
    version: str
    author: str
    description: str
    plugin_type: str
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict = field(default_factory=dict)
    entry_point: str = ""


class PluginBase(ABC):
    manifest: ClassVar[PluginManifest]

    @abstractmethod
    def validate(self) -> List[str]:
        return []

    def on_load(self):
        pass

    def on_unload(self):
        pass
