import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesTransceiverManuinfo(BaseParser):
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
        result = ParseResult()
        blocks = re.split(r'========Interface\s+(\S+(?:\s+\S+)*)========', raw)
        blocks = [b for b in blocks if b.strip()]
        i = 1
        while i < len(blocks):
            iface_raw = blocks[i-1].strip()
            block = blocks[i].strip() if i < len(blocks) else ''
            iface = normalize_iface(iface_raw)
            row = {
                'interface': iface,
                'normalized_iface': iface,
                'category': 'interface',
            }
            if 'transceiver is absent' in block or "doesn't support DDM" in block:
                row['transceiver_present'] = '否'
                row['vendor_name'] = 'N/A'
                row['vendor_pn'] = 'N/A'
                row['vendor_rev'] = 'N/A'
                row['mfg_date'] = 'N/A'
            else:
                row['transceiver_present'] = '是'
                for line in block.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        k, v = line.split(':', 1)
                        k = k.strip()
                        v = v.strip()
                        if 'Vendor Name' in k: row['vendor_name'] = v
                        elif 'Vendor Part Number' in k: row['vendor_pn'] = v
                        elif 'Vendor Revision' in k: row['vendor_rev'] = v
                        elif 'Manufacturing Date' in k: row['mfg_date'] = v
            result.rows.append(row)
            i += 2
        return result
