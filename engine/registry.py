import importlib
import inspect
import logging
import os
import pkgutil
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("switch-inspector.registry")

import yaml

from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.plugin_base import PluginBase, PluginManifest
from engine.plugin_manager import PluginManager
from engine.plugin_exceptions import PluginValidationError
from engine.normalizer import normalize_iface


def _load_mapping(path: str = None) -> Tuple[Dict, Dict]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'textfsm_mapping.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    templates = {}
    for cmd, info in data.get('templates', {}).items():
        templates[cmd] = (
            info['template'],
            info.get('category', 'device'),
            info.get('join_group'),
            info.get('join_key'),
        )
    field_labels = data.get('field_labels', {})
    return templates, field_labels


def _structured_error(
    plugin: str,
    severity: str,
    message: str,
    suggestion: str = "",
) -> Dict[str, str]:
    """Create a structured load error entry.

    Args:
        plugin: Plugin/module name (e.g. ``parsers/foo.py``).
        severity: One of ``"critical"``, ``"warning"``, ``"info"``.
        message: Human-readable error description.
        suggestion: Optional remediation hint.

    Returns:
        A dict with keys ``plugin``, ``severity``, ``message``, ``suggestion``.
    """
    return {
        "plugin": plugin,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
    }


class ParserRegistry:
    def __init__(self):
        self._textfsm_enabled = False
        self._textfsm_parsers: Dict[str, "TextFSMWrapper"] = {}
        self._custom_parsers: Dict[str, BaseParser] = {}
        self._load_errors: List[Dict[str, str]] = []

    def register_textfsm(self, wrapper: "TextFSMWrapper"):
        self._textfsm_parsers[wrapper.command] = wrapper

    def register_custom(self, parser: BaseParser):
        self._custom_parsers[parser.command] = parser

    def has(self, command: str) -> bool:
        return command in self._textfsm_parsers or command in self._custom_parsers

    def all_fields(self) -> List[FieldDef]:
        seen = set()
        fields = []
        for p in self._textfsm_parsers.values():
            for f in p.fields:
                if f.key not in seen:
                    seen.add(f.key)
                    fields.append(f)
        for p in self._custom_parsers.values():
            for f in p.fields:
                if f.key not in seen:
                    seen.add(f.key)
                    fields.append(f)
        return fields

    def get_fields_for_command(self, command: str) -> List[FieldDef]:
        p = self._textfsm_parsers.get(command) or self._custom_parsers.get(command)
        return p.fields if p else []

    def get_load_errors(self) -> List[str]:
        """Return load errors as plain strings (backward-compatible)."""
        return [e["message"] for e in self._load_errors]

    def get_structured_load_errors(self) -> List[Dict[str, str]]:
        """Return load errors as structured dicts with severity/suggestion."""
        return list(self._load_errors)

    def parse(self, command: str, raw: str) -> Optional[ParseResult]:
        result = None

        if self._textfsm_enabled and command in self._textfsm_parsers:
            try:
                result = self._textfsm_parsers[command].parse(raw)
                if result and result.rows:
                    return result
            except Exception as e:
                result = ParseResult(errors=[f"TextFSM failed: {e}"])

        if command in self._custom_parsers:
            result = self._custom_parsers[command].parse(raw)
            if result and result.rows:
                return result

        return result

    def resolve(self, command: str, raw: str) -> ParseResult:
        result = self.parse(command, raw)
        return result if result else ParseResult()

    def load_custom_parsers(self):
        from parsers import __path__ as parsers_paths
        for importer, modname, ispkg in pkgutil.iter_modules(parsers_paths):
            if modname.startswith('_'):
                continue
            try:
                module = importlib.import_module(f"parsers.{modname}")
                found = False
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, BaseParser)
                            and obj is not BaseParser and hasattr(obj, 'command')
                            and obj.command):
                        instance = obj()
                        self.register_custom(instance)
                        found = True
                if not found:
                    self._load_errors.append(_structured_error(
                        f"parsers/{modname}.py", "warning",
                        "no BaseParser subclass found",
                        "Add a class that inherits from BaseParser with a valid 'command' attribute",
                    ))
            except SyntaxError as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "critical",
                    f"语法错误: {e}",
                    "Fix the Python syntax error in this file",
                ))
            except ImportError as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "critical",
                    f"导入失败: {e}",
                    "Check that all dependencies are installed and the module path is correct",
                ))
            except Exception as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "warning",
                    str(e),
                    "Review the parser code for runtime errors",
                ))

    def load_textfsm_parsers(self, mapping_path: str = None):
        try:
            from ntc_templates import parse_output
            self._textfsm_enabled = True
        except ImportError:
            logger.warning("ntc-templates not installed, TextFSM engine disabled")
            return

        try:
            template_map, field_labels = _load_mapping(mapping_path)
        except Exception as e:
            self._load_errors.append(_structured_error(
                "textfsm_mapping.yaml", "critical",
                f"加载 textfsm_mapping.yaml 失败: {e}",
                "Ensure templates/textfsm_mapping.yaml exists and is valid YAML",
            ))
            return

        for cmd, (tmpl, category, join_group, join_key) in template_map.items():
            wrapper = TextFSMWrapper(cmd, tmpl, category, join_group, join_key, field_labels)
            self.register_textfsm(wrapper)

    def initialize(self, mapping_path: str = None):
        self._load_errors = []
        self.load_textfsm_parsers(mapping_path)
        self.load_custom_parsers()

        overlap = set(self._textfsm_parsers.keys()) & set(self._custom_parsers.keys())
        if overlap:
            logger.info("Custom parsers override TextFSM for: %s", overlap)


class TextFSMWrapper(BaseParser):
    def __init__(self, command: str, template_name: str,
                 default_category: str = "interface",
                 join_group: str = None, join_key: str = None,
                 field_labels: Dict[str, str] = None):
        self.command = command
        self._tmpl = template_name
        self._default_category = default_category
        self._join_group = join_group
        self._join_key = join_key
        self._field_labels = field_labels or {}
        self.fields = []

    def _infer_category(self, key: str) -> str:
        k = key.lower()
        if any(x in k for x in ['neighbor', 'chassis', 'system_name', 'mgmt_addr']):
            return 'neighbor'
        if any(x in k for x in ['fan', 'power_supply', 'temperature', 'coredump']):
            return 'system'
        if any(x in k for x in ['log', 'message', 'facility', 'severity', 'seq']):
            return 'log'
        return self._default_category or 'device'

    def _infer_join_group(self, key: str) -> Optional[str]:
        k = key.lower()
        if any(x in k for x in ['neighbor', 'chassis', 'system_name']):
            return 'neighbor'
        if any(x in k for x in ['interface', 'port', 'vlan']) and 'neighbor' not in k:
            return 'interface'
        return self._join_group

    def _infer_join_key(self, key: str) -> Optional[str]:
        kg = self._infer_join_group(key)
        if kg == 'interface':
            return 'normalized_iface'
        if kg == 'neighbor':
            return 'local_iface'
        return None

    def parse(self, raw: str) -> Optional[ParseResult]:
        try:
            from ntc_templates import parse_output
            rows = parse_output(platform="ruijie_os",
                                 command=self.command,
                                 data=raw)
        except Exception as e:
            return ParseResult(errors=[f"TextFSM {self.command}: {e}"])

        if not isinstance(rows, list) or not rows:
            return ParseResult(errors=[f"TextFSM {self.command}: empty result"])

        if not self.fields:
            self.fields = []
            for k in rows[0].keys():
                cat = self._infer_category(k)
                jg = self._infer_join_group(k)
                jk = self._infer_join_key(k)
                label = self._field_labels.get(k.lower(), k)
                self.fields.append(FieldDef(
                    key=k, label=label, category=cat,
                    join_group=jg, join_key=jk,
                ))

        for row in rows:
            for k in row:
                if k.lower() == 'interface' and '/' in str(row[k]):
                    row['normalized_iface'] = normalize_iface(str(row[k]))
                    break
                if k.lower() == 'port' and '/' in str(row[k]):
                    row['normalized_iface'] = normalize_iface(str(row[k]))
                    break
            row['category'] = self._default_category
            row['_origin'] = 'textfsm'

        return ParseResult(rows=rows)


# ── Plugin integration ──────────────────────────────────────────────────


def _wrap_plugin(plugin: PluginBase) -> BaseParser:
    """Wrap a PluginBase instance into a BaseParser-compatible adapter.

    The adapter delegates ``command``, ``fields``, and ``parse()`` to the
    underlying plugin so it can be registered in ``_custom_parsers``.
    """
    class PluginParserAdapter(BaseParser):
        def __init__(self, _p):
            self._p = _p
            self.command = getattr(_p, 'command', '')
            self.fields = getattr(_p, 'fields', [])

        def parse(self, raw: str) -> ParseResult:
            return self._p.parse(raw)

    return PluginParserAdapter(plugin)


def _auto_manifest(cls: type) -> PluginManifest:
    """Generate a default PluginManifest for old-style (non-PluginBase) parsers."""
    return PluginManifest(
        name=cls.__name__,
        version="0.0.0",
        author="auto",
        description=f"Auto-generated manifest for {cls.__name__}",
        plugin_type="parser",
    )


class PluginAwareParserRegistry(ParserRegistry):
    """ParserRegistry that discovers PluginBase parsers via PluginManager.

    * New-style parsers (``PluginBase`` subclasses) are discovered,
      validated, and wrapped via ``_wrap_plugin``.
    * Old-style parsers (``BaseParser`` subclasses without ``PluginBase``)
      are loaded as before, with an auto-generated ``PluginManifest``.
    * Parsers whose ``validate()`` fails are skipped and reported in
      ``_load_errors`` / ``get_load_errors()``.
    """

    def load_custom_parsers(self):
        from parsers import __path__ as parsers_paths
        pm = PluginManager()

        for importer, modname, ispkg in pkgutil.iter_modules(parsers_paths):
            if modname.startswith('_'):
                continue
            try:
                module = importlib.import_module(f"parsers.{modname}")
                plugin_found = False

                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, PluginBase)
                            and obj is not PluginBase):
                        try:
                            instance = obj()
                            pm.register(instance)
                            wrapped = _wrap_plugin(instance)
                            self.register_custom(wrapped)
                            plugin_found = True
                        except PluginValidationError as e:
                            self._load_errors.append(_structured_error(
                                f"parsers/{modname}.py", "warning",
                                f"插件校验失败: {e}",
                                "Check the plugin's validate() method and ensure all required fields are present",
                            ))
                        except Exception as e:
                            self._load_errors.append(_structured_error(
                                f"parsers/{modname}.py", "critical",
                                f"插件加载失败: {e}",
                                "Review the plugin constructor and dependencies",
                            ))

                if not plugin_found:
                    found = False
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and issubclass(obj, BaseParser)
                                and obj is not BaseParser
                                and hasattr(obj, 'command') and obj.command):
                            instance = obj()
                            instance._auto_manifest = _auto_manifest(type(instance))
                            self.register_custom(instance)
                            found = True
                    if not found:
                        self._load_errors.append(_structured_error(
                            f"parsers/{modname}.py", "warning",
                            "no BaseParser subclass found",
                            "Add a class that inherits from BaseParser with a valid 'command' attribute",
                        ))

            except SyntaxError as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "critical",
                    f"语法错误: {e}",
                    "Fix the Python syntax error in this file",
                ))
            except ImportError as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "critical",
                    f"导入失败: {e}",
                    "Check that all dependencies are installed and the module path is correct",
                ))
            except Exception as e:
                self._load_errors.append(_structured_error(
                    f"parsers/{modname}.py", "warning",
                    str(e),
                    "Review the parser code for runtime errors",
                ))
