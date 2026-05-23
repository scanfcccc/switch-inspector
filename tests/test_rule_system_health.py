import pytest

from engine.alert_rule_base import AlertSeverity
from rules.system_health import SystemHealthRule


class TestSystemHealthRule:
    """SystemHealthRule: 设备系统健康状态检测规则."""

    def make_data(self, **extra) -> dict:
        """Helper: build minimal device_data dict."""
        return {
            "device_ip": "10.0.0.1",
            "device_name": "switch-01",
            **extra,
        }

    # ── 1. 全部健康 ──

    def test_all_healthy_no_alerts(self):
        """所有子系统健康 → 无告警."""
        rule = SystemHealthRule()
        data = self.make_data(
            fan_1_status="Normal",
            fan_1_speed="12000",
            temperature_1="45",
            power_1_status="Normal",
        )
        results = rule.evaluate(data)
        assert len(results) == 0

    # ── 2. 风扇故障 ──

    def test_fan_failure_warning(self):
        """风扇状态异常 → WARNING."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["fan"]}
        data = self.make_data(fan_1_status="abnormal")
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert "风扇" in results[0].message

    def test_fan_speed_zero_warning(self):
        """风扇转速为 0 → WARNING."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["fan"]}
        data = self.make_data(fan_1_status="Normal", fan_1_speed="0")
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert "转速" in results[0].message

    # ── 3. 温度超标 ──

    def test_temperature_exceeded_warning(self):
        """温度超过阈值 → WARNING."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["temperature"]}
        data = self.make_data(temperature_1="75")
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert "温度" in results[0].message
        assert "75" in results[0].message

    def test_temperature_below_threshold_no_alert(self):
        """温度低于阈值 → 无告警."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["temperature"]}
        data = self.make_data(temperature_1="45")
        results = rule.evaluate(data)
        assert len(results) == 0

    # ── 4. 电源故障 ──

    def test_power_failure_critical(self):
        """电源状态异常 → CRITICAL."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["power"]}
        data = self.make_data(power_1_status="fail")
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL
        assert "电源" in results[0].message

    def test_power_off_is_critical(self):
        """电源状态为 off → CRITICAL."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["power"]}
        data = self.make_data(power_1_status="off")
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL

    # ── 5. checks 列表排除子系统 ──

    def test_checks_skip_temperature(self):
        """temperature 不在 checks 列表 → 跳过温度检查，即使温度超高."""
        rule = SystemHealthRule()
        rule.config = {"checks": ["fan", "power"]}
        data = self.make_data(
            temperature_1="75",  # 超高但不该检查
            fan_1_status="Normal",
            power_1_status="Normal",
        )
        results = rule.evaluate(data)
        assert len(results) == 0

    def test_checks_empty_skips_all(self):
        """checks 为空列表 → 所有子系统跳过."""
        rule = SystemHealthRule()
        rule.config = {"checks": []}
        data = self.make_data(
            fan_1_status="abnormal",
            temperature_1="75",
            power_1_status="fail",
        )
        results = rule.evaluate(data)
        assert len(results) == 0

    # ── 6. 缺少子系统数据 → INFO ──

    def test_missing_fan_data_info(self):
        """缺少风扇数据且配置检查风扇 → INFO 告警."""
        rule = SystemHealthRule()
        data = self.make_data(
            temperature_1="45",
            power_1_status="Normal",
        )
        results = rule.evaluate(data)
        # 应有 1 条 INFO（风扇缺失），温度/电源正常
        fan_infos = [r for r in results if r.severity == AlertSeverity.INFO
                     and "风扇" in r.message]
        assert len(fan_infos) == 1

    def test_missing_all_subsystem_data_info(self):
        """所有子系统均无数据 → 3 条 INFO 告警."""
        rule = SystemHealthRule()
        data = self.make_data()
        results = rule.evaluate(data)
        assert len(results) == 3
        assert all(r.severity == AlertSeverity.INFO for r in results)
        messages = {r.message for r in results}
        assert "风扇数据未检测到" in messages
        assert "温度数据未检测到" in messages
        assert "电源数据未检测到" in messages

    # ── 7. config — max_temp 自定义阈值 ──

    def test_custom_max_temp(self):
        """自定义 max_temp=80 → 75°C 不告警，85°C 告警."""
        rule = SystemHealthRule()
        rule.config = {"max_temp": 80, "checks": ["temperature"]}

        # 75 < 80 → 无告警
        data_ok = self.make_data(temperature_1="75")
        assert len(rule.evaluate(data_ok)) == 0

        # 85 > 80 → WARNING
        data_fail = self.make_data(temperature_1="85")
        results = rule.evaluate(data_fail)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

    # ── 8. DDM 光功率字段不应触发电源告警 ──

    def test_ddm_power_not_trigger_power_alert(self):
        """ddm_rx_power / ddm_tx_power 是接口级数据，不应触发电源告警."""
        rule = SystemHealthRule()
        data = self.make_data(
            ddm_rx_power="-18.5",
            ddm_tx_power="-5.2",
            fan_1_status="Normal",
            temperature_1="45",
            power_1_status="Normal",
        )
        results = rule.evaluate(data)
        assert len(results) == 0
