"""Tests for OpticsPowerRule — 光功率告警规则。"""

import pytest
from rules.optics_power import OpticsPowerRule
from engine.alert_rule_base import AlertSeverity


# ── helpers ──────────────────────────────────────────────────────────


def _device(interfaces: list = None, ip: str = "10.0.0.1") -> dict:
    """快速构造 device_data 字典。"""
    return {
        "device_ip": ip,
        "device_name": "sw01",
        "interfaces": interfaces or [],
    }


# ── tests ───────────────────────────────────────────────────────────


class TestOpticsPowerRuleConfig:
    """配置读取相关测试。"""

    def test_default_thresholds(self):
        """无 config 时应使用默认阈值 warn=-15, crit=-20。"""
        rule = OpticsPowerRule()
        # -18 < -15 (warn) 且 > -20 (crit), 应产生 WARNING
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-18.0"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

        # -22 < -20 (crit), 应产生 CRITICAL
        results2 = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-22.0"},
        ]))
        assert len(results2) == 1
        assert results2[0].severity == AlertSeverity.CRITICAL

    def test_config_thresholds_used(self):
        """config 中自定义的阈值应覆盖默认值。"""
        rule = OpticsPowerRule()
        rule.config = {"warn": -10, "crit": -18}

        # RX = -12, 默认阈值不会告警(-12 > -15), 但自定义 warn=-10 → WARNING
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-12.0"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert results[0].details["threshold_dbm"] == -10.0

        # RX = -19, 默认阈值警告(-19 < -15), 自定义 crit=-18 → CRITICAL
        results2 = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-19.0"},
        ]))
        assert len(results2) == 1
        assert results2[0].severity == AlertSeverity.CRITICAL
        assert results2[0].details["threshold_dbm"] == -18.0

    def test_config_partial_override(self):
        """部分配置只覆盖其中一个阈值。"""
        rule = OpticsPowerRule()
        rule.config = {"warn": -12}  # crit 使用默认 -20

        # RX = -18, 比自定义 warn=-12 低 → WARNING
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-18.0"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

        # RX = -22, 比默认 crit=-20 低 → CRITICAL
        results2 = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-22.0"},
        ]))
        assert len(results2) == 1
        assert results2[0].severity == AlertSeverity.CRITICAL


class TestOpticsPowerRuleEvaluation:
    """告警评估逻辑测试。"""

    def test_rx_below_warning(self):
        """RX < -15 dBm → WARNING。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-16.5"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING
        assert results[0].interface == "Gi0/1"
        assert results[0].device_ip == "10.0.0.1"
        assert "RX" in results[0].message
        assert "16" in results[0].message

    def test_rx_below_critical(self):
        """RX < -20 dBm → CRITICAL。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-23.8"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL
        assert results[0].interface == "Gi0/1"

    def test_rx_at_threshold_boundary(self):
        """边界值: 恰好等于阈值不应触发(严格小于)。"""
        rule = OpticsPowerRule()
        # warn = -15, RX = -15.0 → NOT < -15 → no alert
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-15.0"},
        ]))
        assert len(results) == 0

        # crit = -20, RX = -20.0 → NOT < -20 (no CRITICAL)
        #                → IS < -15  → WARNING (因为 -20 < -15)
        results2 = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-20.0"},
        ]))
        assert len(results2) == 1
        assert results2[0].severity == AlertSeverity.WARNING

    def test_normal_power_no_alert(self):
        """正常光功率 → 无告警。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-5.0"},
            {"name": "Gi0/2", "ddm_rx_power": "-10.2"},
        ]))
        assert len(results) == 0

    def test_no_transceiver_data_no_alert(self):
        """无光模块数据的接口 → 跳过, 不告警。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "status": "up", "vlan": "100"},
            {"name": "Gi0/2", "status": "down"},
        ]))
        assert len(results) == 0

    def test_no_interfaces_no_alert(self):
        """没有 interfaces 字段 → 无告警。"""
        rule = OpticsPowerRule()
        results = rule.evaluate({"device_ip": "10.0.0.1"})
        assert len(results) == 0

        results2 = rule.evaluate({"device_ip": "10.0.0.1", "interfaces": []})
        assert len(results2) == 0

    def test_mixed_interfaces(self):
        """多个接口混有正常/异常。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_rx_power": "-18.5", "status": "up"},
            {"name": "Gi0/2", "ddm_rx_power": "-5.0", "status": "up"},
            {"name": "Gi0/3", "status": "up"},  # 无光模块数据
            {"name": "Gi0/4", "ddm_rx_power": "-25.0", "status": "up"},
        ]))
        # Gi0/1: WARNING, Gi0/4: CRITICAL
        assert len(results) == 2
        assert results[0].interface == "Gi0/1"
        assert results[0].severity == AlertSeverity.WARNING
        assert results[1].interface == "Gi0/4"
        assert results[1].severity == AlertSeverity.CRITICAL


class TestOpticsPowerRuleFieldMatching:
    """字段名灵活匹配测试。"""

    def test_chinese_field_name(self):
        """中文字段名 'RX 光功率(dBm)' 应被识别。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "RX 光功率(dBm)": "-17.2"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.WARNING

    def test_tx_power_in_details(self):
        """TX 功率和温度应出现在 details 中。"""
        rule = OpticsPowerRule()
        results = rule.evaluate(_device([
            {
                "name": "Gi0/1",
                "ddm_rx_power": "-18.0",
                "ddm_tx_power": "-5.0",
                "ddm_temperature": "42.5",
            },
        ]))
        assert len(results) == 1
        details = results[0].details
        assert details["rx_power_dbm"] == pytest.approx(-18.0)
        assert details["tx_power_dbm"] == pytest.approx(-5.0)
        assert details["temperature_celsius"] == pytest.approx(42.5)

    def test_field_name_variations(self):
        """各种可能的字段命名风格。"""
        rule = OpticsPowerRule()

        # rx_power 风格
        r1 = rule.evaluate(_device([
            {"name": "Gi0/1", "rx_power": "-16.0"},
        ]))
        assert len(r1) == 1

        # rx_power_dbm 风格
        r2 = rule.evaluate(_device([
            {"name": "Gi0/1", "rx_power_dbm": "-16.0"},
        ]))
        assert len(r2) == 1

        # RX power(dBm) 风格
        r3 = rule.evaluate(_device([
            {"name": "Gi0/1", "RX power(dBm)": "-16.0"},
        ]))
        assert len(r3) == 1

    def test_rx_only_matching_not_tx(self):
        """RX 匹配不应被 TX 字段误触发。"""
        rule = OpticsPowerRule()
        # 只有 TX 字段, 不应被当作 RX 数据
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "ddm_tx_power": "-5.0"},
        ]))
        assert len(results) == 0


class TestOpticsPowerRuleValidate:
    """validate() 基本校验。"""

    def test_validate_passes(self):
        """实例应通过自有校验。"""
        rule = OpticsPowerRule()
        errors = rule.validate()
        assert errors == []

    def test_name_and_description_set(self):
        """类变量应正确设置。"""
        assert OpticsPowerRule.name == "optics_power"
        assert OpticsPowerRule.description == "光模块功率异常检测"
