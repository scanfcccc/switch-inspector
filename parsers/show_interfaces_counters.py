import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesCountersErrors(BaseParser):
    command = "show interfaces counters errors"
    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="undersize", label="UnderSize错误", category="interface", dtype="int"),
        FieldDef(key="oversize", label="OverSize错误", category="interface", dtype="int"),
        FieldDef(key="collisions", label="冲突", category="interface", dtype="int"),
        FieldDef(key="fragments", label="碎片", category="interface", dtype="int"),
        FieldDef(key="jabbers", label="Jabber错误", category="interface", dtype="int"),
        FieldDef(key="crc_align_err", label="CRC对齐错误", category="interface", dtype="int"),
        FieldDef(key="align_err", label="对齐错误", category="interface", dtype="int"),
        FieldDef(key="fcs_err", label="FCS错误", category="interface", dtype="int"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        parts = raw.strip().split('Interface')
        if len(parts) < 2:
            return result

        remaining = 'Interface' + parts[1]
        tables = re.split(r'\n(?=Interface)', remaining)
        first_pass = True

        for table in tables:
            lines = table.strip().split('\n')
            header_end = 0
            for i, line in enumerate(lines):
                if all(c in ' -' for c in line):
                    header_end = i + 1
                    break
                if 'Interface' in line and i > 0:
                    header_end = i
                    break

            data_lines = [l for l in lines[header_end:] if l.strip() and not all(c in ' -' for c in l)]

            for idx, line in enumerate(data_lines):
                parts = line.strip().split()
                if len(parts) >= 5:
                    iface_short = parts[0]
                    iface = normalize_iface(iface_short)
                    row = {
                        'interface': iface,
                        'normalized_iface': iface,
                        'category': 'interface',
                    }
                    if first_pass:
                        row.update({
                            'undersize': parts[1], 'oversize': parts[2],
                            'collisions': parts[3], 'fragments': parts[4],
                        })
                    else:
                        row.update({
                            'jabbers': parts[1], 'crc_align_err': parts[2],
                            'align_err': parts[3], 'fcs_err': parts[4],
                        })
                    result.rows.append(row)
                elif len(parts) >= 1 and not parts[0][0].isalpha():
                    continue
            first_pass = False

        return result


class ShowInterfacesCountersRate(BaseParser):
    command = "show interfaces counters rate up"
    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="input_rate_bps", label="入向速率(bps)", category="interface", dtype="int"),
        FieldDef(key="input_rate_pps", label="入向速率(pps)", category="interface", dtype="int"),
        FieldDef(key="output_rate_bps", label="出向速率(bps)", category="interface", dtype="int"),
        FieldDef(key="output_rate_pps", label="出向速率(pps)", category="interface", dtype="int"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        lines = [l for l in raw.strip().split('\n') if l.strip()]
        header_found = False
        for line in lines:
            if 'Input Rate' in line and 'Output Rate' in line:
                header_found = True
                continue
            if not header_found:
                continue
            if all(c in '- ' for c in line):
                continue
            parts = line.strip().split()
            if len(parts) >= 5:
                iface_short = parts[0]
                iface = normalize_iface(iface_short)
                result.rows.append({
                    'interface': iface,
                    'normalized_iface': iface,
                    'input_rate_bps': parts[1],
                    'input_rate_pps': parts[2],
                    'output_rate_bps': parts[3],
                    'output_rate_pps': parts[4],
                    'category': 'interface',
                })
        return result
