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

    KEY_MAP = {
        'Vendor Name': 'vendor_name',
        'Vendor Part Number': 'vendor_pn',
        'Vendor Revision': 'vendor_rev',
        'Manufacturing Date': 'mfg_date',
        'Vendor OUI': 'vendor_oui',
        'Encoding': 'encoding',
    }

    def parse(self, raw: str) -> ParseResult:
        result = super().parse(raw)
        for row in result.rows:
            for old_key, new_key in self.KEY_MAP.items():
                if old_key in row:
                    row[new_key] = row.pop(old_key)
            row['normalized_iface'] = normalize_iface(row.get('interface', ''))
            row['category'] = 'interface'
        return result
