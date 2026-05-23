import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from engine.parser_base import BaseParser, FieldDef, ParseResult


class ParserRegistry:
    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}

    def register(self, parser: BaseParser):
        self._parsers[parser.command] = parser

    def get(self, command: str) -> Optional[BaseParser]:
        return self._parsers.get(command)

    def has(self, command: str) -> bool:
        return command in self._parsers

    def all_fields(self) -> List[FieldDef]:
        seen = set()
        fields = []
        for parser in self._parsers.values():
            for f in parser.fields:
                if f.key not in seen:
                    seen.add(f.key)
                    fields.append(f)
        return fields

    def parse(self, command: str, raw: str) -> Optional[ParseResult]:
        parser = self.get(command)
        if parser:
            return parser.parse(raw)
        return None

    def load_parsers(self, parsers_package: str = "parsers"):
        from parsers import __path__ as parsers_paths
        for importer, modname, ispkg in pkgutil.iter_modules(parsers_paths):
            if modname.startswith('_'):
                continue
            try:
                module = importlib.import_module(f"parsers.{modname}")
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, BaseParser)
                            and obj is not BaseParser and hasattr(obj, 'command')
                            and obj.command):
                        instance = obj()
                        self.register(instance)
            except Exception as e:
                print(f"Failed to load parser {modname}: {e}")

    def load_textfsm_parsers(self):
        try:
            from ntc_templates import parse_output
        except ImportError:
            print("ntc-templates not installed, skipping TextFSM parsers")
            return

        template_map = {
            "show version": "ruijie_os_show_version",
            "show clock": "ruijie_os_show_clock",
            "show version slots": "ruijie_os_show_version_slots",
            "show manuinfo": "ruijie_os_show_manuinfo",
            "show interfaces description": "ruijie_os_show_interfaces_description",
            "show interfaces transceiver": "ruijie_os_show_interfaces_transceiver",
            "show interfaces status": "ruijie_os_show_interfaces_status",
            "show vlan": "ruijie_os_show_vlan",
            "show logging": "ruijie_os_show_logging",
            "show lldp neighbors detail": "ruijie_os_show_lldp_neighbors_detail",
            "show fan speed": "ruijie_os_show_fan",
            "show aggregatePort summary": "ruijie_os_show_aggregatePort_summary",
            "show interfaces counters rate": "ruijie_os_show_interfaces_counters_rate",
            "show vrrp": "ruijie_os_show_vrrp",
            "show arp": "ruijie_os_show_arp",
            "show mac-address-table": "ruijie_os_show_mac-address-table",
        }

        for cmd, tmpl in template_map.items():
            if cmd not in self._parsers:
                self._parsers[cmd] = TextFSMWrapper(cmd, tmpl)


class TextFSMWrapper(BaseParser):
    def __init__(self, command: str, template_name: str):
        self.command = command
        self._tmpl = template_name
        self.fields = [FieldDef(key="textfsm_raw", label=command,
                                 category="interface", description="TextFSM parsed output")]

    def parse(self, raw: str) -> Optional[ParseResult]:
        try:
            from ntc_templates import parse_output
            result = parse_output(platform="ruijie_os",
                                   command=self.command,
                                   data=raw)
            if isinstance(result, list):
                pr = ParseResult(rows=result)
                if result:
                    self.fields = [
                        FieldDef(key=k, label=k, category="interface",
                                 join_group="interface", join_key="normalized_iface")
                        for k in result[0].keys()
                    ]
                return pr
        except Exception as e:
            return ParseResult(errors=[f"TextFSM parse failed: {e}"])
        return None
