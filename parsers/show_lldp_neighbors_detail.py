import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface, normalize_port_id


class ShowLldpNeighborsDetail(BaseParser):
    command = "show lldp neighbors detail"
    fields = [
        FieldDef(key="interface", label="本端接口", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_name", label="邻居设备名", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_ip", label="邻居IP", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_interface", label="邻居端口", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_model", label="邻居型号", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_chassis_id", label="邻居ChassisID", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        blocks = re.split(r'-{3,}', raw)
        for block in blocks:
            block = block.strip()
            if not block or 'LLDP neighbor-information' not in block:
                continue

            row = {'category': 'neighbor'}
            for line in block.split('\n'):
                line = line.strip()
                if 'port [' in line:
                    m = re.search(r'port \[(.+?)\]', line)
                    if m:
                        row['interface'] = normalize_iface(m.group(1))
                elif 'System name' in line and ':' in line:
                    row['neighbor_name'] = line.split(':', 1)[1].strip()
                    row['normalized_neighbor_name'] = row['neighbor_name']
                elif 'System description' in line and ':' in line:
                    desc = line.split(':', 1)[1].strip()
                    m2 = re.search(r'\((\S+)\)', desc)
                    if m2:
                        row['neighbor_model'] = m2.group(1)
                    else:
                        row['neighbor_model'] = desc
                elif 'Management address' in line and ':' in line:
                    row['neighbor_ip'] = line.split(':', 1)[1].strip()
                elif 'Port ID' in line and ':' in line and 'Port ID type' not in line:
                    val = line.split(':', 1)[1].strip()
                    row['neighbor_interface'] = normalize_port_id(val)
                elif 'Chassis ID' in line and ':' in line and 'Chassis ID type' not in line:
                    row['neighbor_chassis_id'] = line.split(':', 1)[1].strip()

            if 'interface' in row:
                row['local_iface'] = row['interface']
                result.rows.append(row)

        return result
