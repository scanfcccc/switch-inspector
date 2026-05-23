from typing import List, Dict, Any

from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity


# 需要监控的错误相关关键字（大小写不敏感）
ERROR_KEY_PATTERNS = [
    "error", "crc", "frame", "runt", "giant", "discard", "drop",
]


class InterfaceErrorsRule(AlertRule):
    """接口错误计数异常检测规则。

    扫描每个接口下与错误相关的计数器字段，若超出阈值则产生告警。
    - 阈值由 config["max_errors"] 控制，默认 100。
    - 任一计数器 > max_errors × 10 → CRITICAL
    - 任一计数器 > max_errors → WARNING
    """

    name = "interface_errors"
    description = "接口错误计数异常检测"

    # ── 辅助：提取接口名称 ──

    @staticmethod
    def _get_ifname(iface: dict) -> str:
        return str(iface.get("name") or iface.get("interface") or "")

    # ── 辅助：收集错误计数器 ──

    @staticmethod
    def _collect_error_counters(iface: dict) -> Dict[str, int]:
        """返回接口字典中所有与错误相关的数值计数器（>0）。"""
        counters: Dict[str, int] = {}
        for key, value in iface.items():
            # 跳过内部元字段
            if key.startswith("_"):
                continue
            # 检查关键字匹配
            key_lower = key.lower()
            if not any(p in key_lower for p in ERROR_KEY_PATTERNS):
                continue
            # 尝试转换为整数
            try:
                val = int(value) if value is not None else 0
            except (ValueError, TypeError):
                continue
            if val > 0:
                counters[key] = val
        return counters

    # ── 核心评估方法 ──

    def evaluate(self, device_data: dict) -> List[AlertResult]:
        results: List[AlertResult] = []
        max_errors = int(self.config.get("max_errors", 100))
        if max_errors <= 0:
            max_errors = 100

        interfaces: List[dict] = device_data.get("interfaces", [])
        device_ip: str = device_data.get("device_ip", "") or ""

        for iface in interfaces:
            if_name = self._get_ifname(iface)
            if not if_name:
                continue

            counters = self._collect_error_counters(iface)
            if not counters:
                continue

            # 计算当前接口的最大计数器值
            max_val = max(counters.values())
            max_key = max(counters, key=counters.get)

            # 判断严重等级
            if max_val > max_errors * 10:
                severity = AlertSeverity.CRITICAL
            elif max_val > max_errors:
                severity = AlertSeverity.WARNING
            else:
                continue

            results.append(AlertResult(
                rule_name=self.name,
                severity=severity,
                message=f"接口 {if_name} 错误计数异常: {max_key}={max_val}",
                device_ip=device_ip,
                interface=if_name,
                details={
                    "max_errors": max_errors,
                    "error_counters": counters,
                    "worst_key": max_key,
                    "worst_value": max_val,
                },
            ))

        return results
