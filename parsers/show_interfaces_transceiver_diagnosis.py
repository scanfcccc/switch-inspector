import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesTransceiverDiagnosis(BaseParser):
    command = "show interfaces transceiver diagnosis"
    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_temperature", label="温度(°C)", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_voltage", label="电压(V)", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_bias", label="偏置电流(mA)", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_rx_power", label="RX光功率(dBm)", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_tx_power", label="TX光功率(dBm)", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="ddm_present", label="DDM数据", category="interface",
                 join_group="interface", join_key="normalized_iface"),
    ]

    DDM_HEADER = re.compile(
        r'Temp\(Celsius\)\s+Voltage\(V\)\s+Bias\(mA\)\s+RX\s+power\(dBm\)\s+TX\s+power\(dBm\)'
    )
    DDM_DATA = re.compile(
        r'^\s*([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)'
    )

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        # Split by interface delimiter
        sections = re.split(r'(=======+Interface\s+\S+(?:\s+\S+)*========)', raw)
        if len(sections) < 3:
            return result

        for i in range(1, len(sections), 2):
            delimiter = sections[i].strip()
            content = sections[i + 1] if i + 1 < len(sections) else ''

            iface_match = re.search(r'Interface[ \t]+([^=\n]+[^=\s])', delimiter)
            iface_name = iface_match.group(1).strip() if iface_match else ''
            if not iface_name:
                continue

            iface = normalize_iface(iface_name)
            row = {
                'interface': iface,
                'normalized_iface': iface,
                'category': 'interface',
            }

            # Check if DDM data exists
            if 'transceiver is absent' in content or "doesn't support DDM" in content:
                row['ddm_present'] = '否'
                row['ddm_temperature'] = ''
                row['ddm_voltage'] = ''
                row['ddm_bias'] = ''
                row['ddm_rx_power'] = ''
                row['ddm_tx_power'] = ''
                result.rows.append(row)
                continue

            # Find DDM data line
            ddm_match = self.DDM_DATA.search(content)
            if ddm_match:
                rx_raw = ddm_match.group(4)
                tx_raw = ddm_match.group(5)
                rx_clean = re.sub(r'\(.*?\)', '', rx_raw).replace('[OMA]', '').replace('[AP]', '').strip()
                tx_clean = re.sub(r'\(.*?\)', '', tx_raw).replace('[OMA]', '').replace('[AP]', '').strip()
                try:
                    rx_float = float(rx_clean)
                    tx_float = float(tx_clean)
                    if -50 <= rx_float <= 10 and -50 <= tx_float <= 10:
                        row['ddm_rx_power'] = f'{rx_clean}'
                        row['ddm_tx_power'] = f'{tx_clean}'
                    else:
                        row['ddm_rx_power'] = rx_clean
                        row['ddm_tx_power'] = tx_clean
                except ValueError:
                    row['ddm_rx_power'] = rx_clean
                    row['ddm_tx_power'] = tx_clean

                row['ddm_temperature'] = ddm_match.group(1)
                row['ddm_voltage'] = ddm_match.group(2)
                row['ddm_bias'] = ddm_match.group(3)
                row['ddm_present'] = '是'
            else:
                row['ddm_present'] = '否'

            result.rows.append(row)

        return result


class ShowInterfaceTransceiverDiagnosis(ShowInterfacesTransceiverDiagnosis):
    command = "show interface transceiver diagnosis"
