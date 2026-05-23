from typing import Dict, List, Optional, Any
from engine.plugin_base import PluginBase, PluginManifest
from engine.plugin_exceptions import PluginValidationError, PluginRuntimeError


class PluginManager:
    def __init__(self):
        self._registry: Dict[str, Dict[str, PluginBase]] = {}

    def register(self, plugin: PluginBase) -> None:
        ptype = plugin.manifest.plugin_type
        errors = plugin.validate()
        if errors:
            raise PluginValidationError(
                f"{plugin.manifest.name}: {', '.join(errors)}"
            )
        if ptype not in self._registry:
            self._registry[ptype] = {}
        self._registry[ptype][plugin.manifest.name] = plugin

    def discover(self, directory: str) -> List[str]:
        import importlib
        import inspect
        import pkgutil

        found = []
        for importer, modname, ispkg in pkgutil.iter_modules([directory]):
            if modname.startswith("_"):
                continue
            module = importlib.import_module(modname)
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginBase)
                    and obj is not PluginBase
                ):
                    try:
                        instance = obj()
                        self.register(instance)
                        found.append(instance.manifest.name)
                    except PluginValidationError:
                        pass
        return found

    def get_plugins(self, plugin_type: str) -> List[PluginBase]:
        return list(self._registry.get(plugin_type, {}).values())

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        for plugins in self._registry.values():
            if name in plugins:
                return plugins[name]
        return None

    def execute(
        self, plugin_type: str, method: str, *args, **kwargs
    ) -> List[Any]:
        results = []
        for plugin in self.get_plugins(plugin_type):
            try:
                fn = getattr(plugin, method)
                results.append(fn(*args, **kwargs))
            except Exception:
                results.append(None)
        return results

    def topological_order(
        self, plugins: List[PluginBase]
    ) -> List[PluginBase]:
        from collections import deque, defaultdict

        graph = {
            p.manifest.name: set(p.manifest.dependencies) for p in plugins
        }
        in_degree: Dict[str, int] = {name: 0 for name in graph}
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        ordered_names = []
        while queue:
            name = queue.popleft()
            ordered_names.append(name)
            for other_name, deps in graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        name_to_plugin = {p.manifest.name: p for p in plugins}
        return [
            name_to_plugin[n]
            for n in ordered_names
            if n in name_to_plugin
        ]

    def load_all(self, plugin_dirs: List[str]) -> Dict[str, int]:
        counts = {}
        for d in plugin_dirs:
            found = self.discover(d)
            for name in found:
                p = self.get_plugin(name)
                if p:
                    t = p.manifest.plugin_type
                    counts[t] = counts.get(t, 0) + 1
        return counts

    def unload_all(self):
        for plugins in self._registry.values():
            for plugin in plugins.values():
                try:
                    plugin.on_unload()
                except Exception:
                    pass
        self._registry.clear()


_INSTANCE: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PluginManager()
    return _INSTANCE
