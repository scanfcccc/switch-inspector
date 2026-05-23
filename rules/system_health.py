from typing import List, Optional

from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity

# 风扇 / 电源异常状态关键字（大小写不敏感）
_FAILURE_KEYWORDS = {"abnormal", "fail", "error", "stop"}

# 电源额外的异常关键字
_POWER_FAILURE_KEYWORDS = {"off", "absent"}


class SystemHealthRule(AlertRule):
    """设备系统健康状态检测规则。

    检查三个子系统:
      1. 风扇（Fan）   — 扫描 ``device_data`` 中 key 包含 ``fan`` 的字段，
                        若 status 为 abnormal/stop/fail 或 speed=0 则告警。
      2. 温度（Temperature） — 扫描 key 包含 ``temp`` 的字段，
                              数值超出 ``max_temp``（默认 60°C）则告警。
      3. 电源（Power） — 扫描 key 包含 ``power`` 的字段，
                        若状态为 abnormal/fail/off/absent 则告警。

    Config 选项（通过 ``self.config`` 字典设置）:
        - max_temp: float  — 温度阈值 °C（默认 60）
        - checks: List[str] — 需要检查的子系统列表
          （默认 ["fan", "temperature", "power"]）
    """

    name = "system_health"
    description = "设备系统健康状态检测"

    # ── 公共：扫描匹配关键字的字段 ──

    @staticmethod
    def _find_keys(data: dict, pattern: str) -> List[str]:
        """返回 data 中所有 key 包含 *pattern*（大小写不敏感）的字段名列表。"""
        return [k for k in data if pattern in k.lower()]

    # ── 风扇检查 ──

    def _check_fan(self, data: dict, device_ip: str) -> Optional[AlertResult]:
        fan_keys = self._find_keys(data, "fan")
        if not fan_keys:
            return AlertResult(
                rule_name=self.name,
                severity=AlertSeverity.INFO,
                message="风扇数据未检测到",
                device_ip=device_ip,
            )

        for k in fan_keys:
            v = data[k]
            v_str = str(v).lower().strip()
            if v_str in _FAILURE_KEYWORDS:
                return AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.WARNING,
                    message="风扇异常",
                    device_ip=device_ip,
                    details={"key": k, "value": str(v)},
                )
            # 转速类字段值为 0 也视为故障
            if "speed" in k.lower() or "转速" in k.lower():
                try:
                    if float(v) == 0:
                        return AlertResult(
                            rule_name=self.name,
                            severity=AlertSeverity.WARNING,
                            message="风扇转速为零",
                            device_ip=device_ip,
                            details={"key": k, "value": str(v)},
                        )
                except (ValueError, TypeError):
                    pass
        return None

    # ── 温度检查 ──

    def _check_temperature(
        self, data: dict, device_ip: str, max_temp: float
    ) -> Optional[AlertResult]:
        temp_keys = self._find_keys(data, "temp")
        if not temp_keys:
            return AlertResult(
                rule_name=self.name,
                severity=AlertSeverity.INFO,
                message="温度数据未检测到",
                device_ip=device_ip,
            )

        for k in temp_keys:
            v = data[k]
            try:
                val = float(v)
            except (ValueError, TypeError):
                continue
            if val > max_temp:
                return AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.WARNING,
                    message=f"设备温度 {val}°C 超过阈值 {max_temp}°C",
                    device_ip=device_ip,
                    details={"key": k, "value": str(v), "threshold": max_temp},
                )
        return None

    # ── 电源检查 ──

    def _check_power(self, data: dict, device_ip: str) -> Optional[AlertResult]:
        # 排除 DDM 接口级光功率字段
        power_keys = [
            k for k in data
            if "power" in k.lower() and "ddm" not in k.lower()
        ]
        if not power_keys:
            return AlertResult(
                rule_name=self.name,
                severity=AlertSeverity.INFO,
                message="电源数据未检测到",
                device_ip=device_ip,
            )

        all_failure = _FAILURE_KEYWORDS | _POWER_FAILURE_KEYWORDS
        for k in power_keys:
            v = data[k]
            v_str = str(v).lower().strip()
            if v_str in all_failure:
                return AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.CRITICAL,
                    message="电源异常",
                    device_ip=device_ip,
                    details={"key": k, "value": str(v)},
                )
        return None

    # ── 核心评估方法 ──

    def evaluate(self, device_data: dict) -> List[AlertResult]:
        results: List[AlertResult] = []
        checks = self.config.get("checks", ["fan", "temperature", "power"])
        max_temp = float(self.config.get("max_temp", 60))
        device_ip: str = device_data.get("device_ip", "") or ""

        if "fan" in checks:
            result = self._check_fan(device_data, device_ip)
            if result is not None:
                results.append(result)

        if "temperature" in checks:
            result = self._check_temperature(device_data, device_ip, max_temp)
            if result is not None:
                results.append(result)

        if "power" in checks:
            result = self._check_power(device_data, device_ip)
            if result is not None:
                results.append(result)

        return results
