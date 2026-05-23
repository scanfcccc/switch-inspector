"""光功率告警规则 — 监控光模块 RX/TX 功率和温度。"""

from typing import List, Optional, Dict

from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity


# ── 字段名模糊匹配模式 ──────────────────────────────────────────────
# 每组的 所有 关键词必须同时出现在 key（小写化后）中才算匹配。
_RX_PATTERNS = [
    ["rx_power"],  # ddm_rx_power, rx_power, rx_power_dbm
    ["rx", "power"],  # rxpower, rx_power ...
    ["rx", "dbm"],  # RX 光功率(dBm), RX power(dBm)
    ["rx", "光功率"],  # RX 光功率(dBm), RX光功率(dBm)
]

_TX_PATTERNS = [
    ["tx_power"],  # ddm_tx_power, tx_power
    ["tx", "power"],
    ["tx", "dbm"],
    ["tx", "光功率"],
]

_TEMP_PATTERNS = [
    ["temperature"],  # ddm_temperature, temperature
    ["temp"],
]


def _find_float(iface: dict, patterns: List[List[str]]) -> Optional[float]:
    """在接口字典中按模式组搜索第一个可转换为 float 的值。"""
    for key, value in iface.items():
        kl = key.lower()
        for group in patterns:
            if all(p in kl for p in group):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    continue
    return None


class OpticsPowerRule(AlertRule):
    """光模块功率异常检测规则。

    从 ``show interfaces transceiver diagnosis`` 等解析器产出的接口
    字典中查找 RX 光功率, 并与可配置的阈值比较。
    """

    name = "optics_power"
    description = "光模块功率异常检测"

    def evaluate(self, device_data: dict) -> List[AlertResult]:
        """遍历所有接口, 检查 RX 光功率是否越限。"""
        results: List[AlertResult] = []

        config = self.config or {}
        warn_threshold = float(config.get("warn", -15.0))
        crit_threshold = float(config.get("crit", -20.0))

        device_ip = device_data.get("device_ip", "")
        interfaces = device_data.get("interfaces", [])

        for iface in interfaces:
            rx_power = _find_float(iface, _RX_PATTERNS)
            if rx_power is None:
                continue  # 无光模块数据, 跳过

            iface_name = iface.get("name") or iface.get("interface") or ""

            # 附带收集 TX / 温度信息（仅用于 details）
            details: Dict = {"rx_power_dbm": rx_power}
            tx_power = _find_float(iface, _TX_PATTERNS)
            if tx_power is not None:
                details["tx_power_dbm"] = tx_power
            temp = _find_float(iface, _TEMP_PATTERNS)
            if temp is not None:
                details["temperature_celsius"] = temp

            if rx_power < crit_threshold:
                results.append(
                    AlertResult(
                        rule_name=self.name,
                        severity=AlertSeverity.CRITICAL,
                        message=(
                            f"接口 {iface_name} RX 光功率严重异常: "
                            f"{rx_power:.2f} dBm (阈值: {crit_threshold:.1f} dBm)"
                        ),
                        device_ip=device_ip,
                        interface=iface_name,
                        details={**details, "threshold_dbm": crit_threshold},
                    )
                )
            elif rx_power < warn_threshold:
                results.append(
                    AlertResult(
                        rule_name=self.name,
                        severity=AlertSeverity.WARNING,
                        message=(
                            f"接口 {iface_name} RX 光功率偏低: "
                            f"{rx_power:.2f} dBm (阈值: {warn_threshold:.1f} dBm)"
                        ),
                        device_ip=device_ip,
                        interface=iface_name,
                        details={**details, "threshold_dbm": warn_threshold},
                    )
                )
            # else: normal → no alert

        return results
