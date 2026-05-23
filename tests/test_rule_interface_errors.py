"""接口错误计数告警规则测试. InterfaceErrorsRule."""
from typing import List, Dict

import pytest
from engine.alert_rule_base import AlertSeverity, AlertResult
from rules.interface_errors import InterfaceErrorsRule


class TestInterfaceErrorsRule:
    """InterfaceErrorsRule 的完整行为测试."""

    # ── 辅助方法 ──

    @staticmethod
    def make_rule(config: dict = None) -> InterfaceErrorsRule:
        rule = InterfaceErrorsRule()
        if config:
            rule.config = dict(config)
        return rule

    @staticmethod
    def make_device_data(interfaces: List[Dict],
                         device_ip: str = "10.0.0.1") -> Dict:
        return {
            "device_ip": device_ip,
            "device_name": "switch-01",
            "interfaces": list(interfaces),
        }

    # ── 1. 默认阈值 ──

    def test_default_max_errors(self):
        """默认 max_errors=100，errors=150 应产生 WARNING 告警."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "150", "crc": "50"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert results[0].interface == "Gi0/1"

    # ── 2. 自定义阈值 ──

    def test_custom_max_errors(self):
        """config["max_errors"]=50 时 threshold 降至 50，errors=75 应告警."""
        rule = self.make_rule({"max_errors": 50})
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "75"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

    # ── 3. 低于阈值 ──

    def test_below_threshold_no_alert(self):
        """所有错误计数器均低于默认阈值 100，不应产生告警."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "50", "crc": "30", "runts": "10"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 0

    # ── 4. 超阈值 → WARNING ──

    def test_exceeds_threshold_gives_warning(self):
        """errors=150（>100 但未超过 10×100=1000）应产生 WARNING."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "150"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert results[0].rule_name == "interface_errors"

    # ── 5. 严重超标 → CRITICAL ──

    def test_far_exceeds_threshold_gives_critical(self):
        """errors=2000（>10×100=1000）应产生 CRITICAL."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "2000"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL

    # ── 6. 无错误数据 ──

    def test_no_error_data_skipped(self):
        """接口中没有任何错误相关字段，不应产生告警."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "status": "up", "vlan": "100"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 0

    # ── 7. 混合接口 ──

    def test_partial_error_data(self):
        """多个接口中只有错误超标的产生告警，其余跳过."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "50"},               # 低于阈值 → 不告警
            {"name": "Gi0/2", "errors": "200"},              # WARNING
            {"name": "Gi0/3", "status": "up"},               # 无错误字段 → 不告警
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].interface == "Gi0/2"
        assert results[0].severity == AlertSeverity.WARNING

    # ── 8. 空接口列表 ──

    def test_empty_interfaces(self):
        """空接口列表应返回空列表."""
        rule = self.make_rule()
        data = self.make_device_data([])
        results = rule.evaluate(data)
        assert results == []

    # ── 9. 接口标识键兼容性 ──

    def test_supports_interface_key(self):
        """支持 'interface' 和 'name' 两种接口标识键."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"interface": "Gi0/1", "errors": "150"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].interface == "Gi0/1"

    # ── 10. 大小写不敏感 ──

    def test_case_insensitive_keywords(self):
        """错误相关关键字匹配应大小写不敏感."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "CRC": "200", "Error": "0"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

    # ── 11. 多接口独立评级 ──

    def test_multiple_interfaces_independent_severity(self):
        """不同接口可分别产生 WARNING 和 CRITICAL."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "2000"},  # CRITICAL
            {"name": "Gi0/2", "errors": "150"},   # WARNING
        ])
        results = rule.evaluate(data)
        assert len(results) == 2
        severities = {r.interface: r.severity for r in results}
        assert severities["Gi0/1"] == AlertSeverity.CRITICAL
        assert severities["Gi0/2"] == AlertSeverity.WARNING

    # ── 12. 结果包含 details ──

    def test_result_includes_details(self):
        """告警结果应包含 error_counters、worst_key、worst_value 等明细."""
        rule = self.make_rule()
        data = self.make_device_data([
            {"name": "Gi0/1", "errors": "999", "crc": "500"},
        ])
        results = rule.evaluate(data)
        assert len(results) == 1
        details = results[0].details
        assert details is not None
        assert details["max_errors"] == 100
        assert details["worst_key"] == "errors"
        assert details["worst_value"] == 999
        assert details["error_counters"] == {"errors": 999, "crc": 500}
