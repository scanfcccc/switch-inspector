import re
from typing import Optional, Dict

from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


def _clean_ddm_value(raw: str) -> str:
    """Remove status suffix (e.g. (OK)) and tags (e.g. [AP]) from DDM values."""
    return re.sub(r'\(.*?\)', '', raw).replace('[OMA]', '').replace('[AP]', '').strip()


class ShowInterfacesTransceiverDiagnosis(BaseParser):
    """Parse ``show interfaces transceiver diagnosis`` output.

    Ruijie S5000 输出格式:

        Temp(Celsius)   Voltage(V)      Bias(mA)            RX power(dBm)       TX power(dBm)
        39(OK)          3.25(OK)        49.89(OK)           -4.68(OK)[AP]       -2.00(OK)
        Diagnostic parameters threshold:
        ...
        ========Interface TenGigabitEthernet 0/28========
        Current diagnostic parameters:
        This module doesn't support DDM!
        ========Interface TenGigabitEthernet 0/29========

    DDM 数据行在 ``========Interface========`` 分隔符之前出现。
    """

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

    # DDM 表头行
    DDM_HEADER = re.compile(
        r'Temp\(Celsius\)\s+Voltage\(V\)\s+Bias\(mA\)\s+RX\s+power\(dBm\)\s+TX\s+power\(dBm\)'
    )
    # DDM 数据行 — 兼容有/无 (OK)[AP] 后缀
    _VAL = r'[\d\.\-]+(?:\([^)]*\))?(?:\s*\[[^\]]*\])?'
    DDM_DATA = re.compile(
        rf'^\s*({_VAL})\s+({_VAL})\s+({_VAL})\s+({_VAL})\s+({_VAL})',
        re.MULTILINE
    )

    def _extract_ddm(self, content: str) -> Optional[Dict[str, str]]:
        """从 content 中提取 DDM 数据行, 返回 {ddm_*} dict 或 None。"""
        m = self.DDM_DATA.search(content)
        if not m:
            return None
        try:
            rx_clean = _clean_ddm_value(m.group(4))
            tx_clean = _clean_ddm_value(m.group(5))
            rx_float = float(rx_clean)
            tx_float = float(tx_clean)
        except (ValueError, TypeError):
            return None
        # 合理性校验: RX/TX 功率在正常光模块范围内
        if not (-50 <= rx_float <= 10 and -50 <= tx_float <= 10):
            return None
        return {
            'ddm_temperature': _clean_ddm_value(m.group(1)),
            'ddm_voltage': _clean_ddm_value(m.group(2)),
            'ddm_bias': _clean_ddm_value(m.group(3)),
            'ddm_rx_power': rx_clean,
            'ddm_tx_power': tx_clean,
        }

    def _empty_ddm_row(self) -> Dict[str, str]:
        return {k: '' for k in
                ['ddm_temperature', 'ddm_voltage', 'ddm_bias', 'ddm_rx_power', 'ddm_tx_power']}

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        # Split by interface delimiter. 使用 [ \t] 而非 \s 防止跨行匹配.
        delim_re = r'(========+Interface[ \t]+\S+(?:[ \t]+\S+)*========)'
        sections = re.split(delim_re, raw)
        if len(sections) < 2:
            return result

        # sections[0] = content before first delimiter (DDM preambles)
        pending_content = sections[0]

        for i in range(1, len(sections), 2):
            delimiter = sections[i].strip()
            post_content = sections[i + 1] if i + 1 < len(sections) else ''

            iface_match = re.search(r'Interface[ \t]+([^=\n]+[^=\s])', delimiter)
            iface_name = iface_match.group(1).strip() if iface_match else ''
            if not iface_name:
                pending_content = post_content
                continue

            iface = normalize_iface(iface_name)
            row: Dict = {
                'interface': iface,
                'normalized_iface': iface,
                'category': 'interface',
            }

            # DDM 数据在分隔符之前
            ddm_data = self._extract_ddm(pending_content)
            if ddm_data:
                row.update(ddm_data)
                row['ddm_present'] = '是'
            else:
                row.update(self._empty_ddm_row())
                absent = 'transceiver is absent' in (pending_content + post_content)
                no_ddm = "doesn't support DDM" in (pending_content + post_content)
                row['ddm_present'] = '否' if (absent or no_ddm) else ''

            result.rows.append(row)
            pending_content = post_content

        return result


class ShowInterfaceTransceiverDiagnosis(ShowInterfacesTransceiverDiagnosis):
    command = "show interface transceiver diagnosis"
