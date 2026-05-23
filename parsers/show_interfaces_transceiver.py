import re
from engine.parser_base import BlockParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesTransceiverManuinfo(BlockParser):
    command = "show interfaces transceiver manuinfo"

    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="vendor_name", label="光模块厂商", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="vendor_pn", label="光模块型号", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="vendor_rev", label="光模块版本", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="mfg_date", label="生产日期", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="transceiver_present", label="光模块在位", category="interface",
                 join_group="interface", join_key="normalized_iface"),
    ]

    def parse(self, raw: str) -> ParseResult:
        return super().parse(raw)
