"""风暴控制合规检查规则 — 测试."""

import pytest
from engine.alert_rule_base import AlertSeverity, AlertResult
from rules.storm_control import StormControlRule


# ── 辅助构建 fixture ──

@pytest.fixture
def rule():
    return StormControlRule()


DEVICE_IP = "10.0.0.1"
DEVICE_NAME = "sw1"


def _device(interfaces: list) -> dict:
    return {
        "device_ip": DEVICE_IP,
        "device_name": DEVICE_NAME,
        "interfaces": interfaces,
    }


# ══════════════════════════════════════════════════════════════
# 1. 风暴控制已开启 → 不产生告警
# ══════════════════════════════════════════════════════════════

class TestStormControlEnabled:
    """storm_control / broadcast_suppression 已开启的各种格式."""

    def test_storm_control_string_enable(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},
        ]))
        assert len(results) == 0

    def test_storm_control_string_enabled(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enabled"},
        ]))
        assert len(results) == 0

    def test_storm_control_boolean_true(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": True},
        ]))
        assert len(results) == 0

    def test_storm_control_integer_one(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": 1},
        ]))
        assert len(results) == 0

    def test_storm_control_yes_chinese(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "是"},
        ]))
        assert len(results) == 0

    def test_broadcast_suppression_enabled(self, rule):
        """broadcast_suppression 已开启 → 也视为合规."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "broadcast_suppression": True},
        ]))
        assert len(results) == 0

    def test_multiple_interfaces_all_enabled(self, rule):
        """所有接口均已开启 → 无告警."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},
            {"name": "Gi0/2", "storm_control": True},
            {"name": "Gi0/3", "broadcast_suppression": 1},
        ]))
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════
# 2. 风暴控制显式关闭 → CRITICAL
# ══════════════════════════════════════════════════════════════

class TestStormControlDisabled:
    """storm_control 显式关闭的各种格式."""

    DISABLED_CASES = [
        ("string disable", {"storm_control": "disable"}),
        ("string disabled", {"storm_control": "disabled"}),
        ("boolean False", {"storm_control": False}),
        ("integer zero", {"storm_control": 0}),
        ("float zero", {"storm_control": 0.0}),
        ("string no", {"storm_control": "no"}),
        ("string false", {"storm_control": "false"}),
    ]

    @pytest.mark.parametrize("label,fields", DISABLED_CASES,
                             ids=[c[0] for c in DISABLED_CASES])
    def test_disabled_severity_and_message(self, rule, label, fields):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", **fields},
        ]))
        assert len(results) == 1
        r = results[0]
        assert r.severity == AlertSeverity.CRITICAL
        assert r.rule_name == "storm_control"
        assert r.interface == "Gi0/1"
        assert "风暴控制未开启" in r.message

    def test_broadcast_suppression_disabled(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "broadcast_suppression": "disable"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL
        assert results[0].interface == "Gi0/1"

    def test_multiple_disabled_interfaces(self, rule):
        """多个接口关闭 → 每个接口一条告警."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
            {"name": "Gi0/2", "storm_control": False},
            {"name": "Gi0/3", "storm_control": 0},
        ]))
        assert len(results) == 3
        assert all(r.severity == AlertSeverity.CRITICAL for r in results)


# ══════════════════════════════════════════════════════════════
# 3. 缺少风暴控制字段 + strict=True → CRITICAL
# ══════════════════════════════════════════════════════════════

class TestMissingKeyStrictTrue:
    """缺少 storm_control / broadcast_suppression 且 strict=True."""

    def test_default_strict(self, rule):
        """默认 strict=True → 缺失字段的接口产生 CRITICAL 告警."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},   # has data
            {"name": "Gi0/2", "status": "up"},              # missing
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL
        assert results[0].interface == "Gi0/2"
        assert "缺少风暴控制配置" in results[0].message

    def test_explicit_strict_true(self, rule):
        rule.config = {"strict": True}
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},   # has data
            {"name": "Gi0/2", "something": "else"},         # missing
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL
        assert results[0].details["reason"] == "missing_key"

    def test_mixed_missing_and_enabled(self, rule):
        """部分接口有数据、部分缺失 → 仅缺失的接口产生告警."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},
            {"name": "Gi0/2", "status": "up"},  # missing
            {"name": "Gi0/3", "broadcast_suppression": 1},
        ]))
        assert len(results) == 1
        assert results[0].interface == "Gi0/2"

    def test_all_missing_no_other_storm_data(self, rule):
        """所有接口都缺失且无任何风暴数据 → INFO 而非 CRITICAL."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "status": "up"},
            {"name": "Gi0/2", "status": "down"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.INFO
        assert results[0].interface is None


# ══════════════════════════════════════════════════════════════
# 4. 缺少风暴控制字段 + strict=False → 不产生告警
# ══════════════════════════════════════════════════════════════

class TestMissingKeyStrictFalse:
    """strict=False 时，仅显式关闭才告警，缺少字段不告警."""

    def test_missing_key_no_alert(self, rule):
        """strict=False 时缺少字段不告警，但有数据的接口仍正常处理."""
        rule.config = {"strict": False}
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},   # has data → enabled, ok
            {"name": "Gi0/2", "status": "up"},              # missing, strict=False → no alert
        ]))
        assert len(results) == 0

    def test_strict_false_explicitly_disabled_still_fires(self, rule):
        """strict=False 但显式关闭 → 仍告警."""
        rule.config = {"strict": False}
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL


# ══════════════════════════════════════════════════════════════
# 5. required=False → 完全跳过检查
# ══════════════════════════════════════════════════════════════

class TestRequiredFalse:
    """required=False 跳过整个检查."""

    def test_skips_disabled_interfaces(self, rule):
        rule.config = {"required": False}
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
        ]))
        assert len(results) == 0

    def test_skips_missing_data(self, rule):
        rule.config = {"required": False}
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "status": "up"},
        ]))
        assert len(results) == 0

    def test_skips_empty_interfaces(self, rule):
        rule.config = {"required": False}
        results = rule.evaluate({"device_ip": DEVICE_IP, "interfaces": []})
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════
# 6. 无任何风暴控制数据 → INFO 设备级告警
# ══════════════════════════════════════════════════════════════

class TestNoStormDataAtAll:
    """设备完全没有风暴控制数据 → 单条 INFO 告警."""

    def test_no_storm_keys(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "status": "up"},
            {"name": "Gi0/2", "status": "down"},
        ]))
        assert len(results) == 1
        r = results[0]
        assert r.severity == AlertSeverity.INFO
        assert r.device_ip == DEVICE_IP
        assert r.interface is None
        assert "未提供风暴控制数据" in r.message

    def test_empty_interfaces(self, rule):
        results = rule.evaluate(_device([]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.INFO

    def test_missing_interfaces_key(self, rule):
        results = rule.evaluate({"device_ip": DEVICE_IP, "device_name": DEVICE_NAME})
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.INFO

    def test_interfaces_none(self, rule):
        results = rule.evaluate({"device_ip": DEVICE_IP, "interfaces": None})
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.INFO


# ══════════════════════════════════════════════════════════════
# 7. 边界与混合场景
# ══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界值与混合场景."""

    def test_no_device_ip(self, rule):
        """device_ip 为空字符串时不应出错."""
        results = rule.evaluate({
            "device_ip": "",
            "interfaces": [{"name": "Gi0/1", "storm_control": "disable"}],
        })
        assert len(results) == 1
        assert results[0].device_ip == ""

    def test_interface_name_from_interface_key(self, rule):
        """使用 'interface' 而非 'name' 键."""
        results = rule.evaluate(_device([
            {"interface": "Fa0/1", "storm_control": "disable"},
        ]))
        assert results[0].interface == "Fa0/1"

    def test_unknown_value_considered_disabled(self, rule):
        """未知字符串视为关闭."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "unknown_value"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL

    def test_strict_true_with_some_but_not_all_missing(self, rule):
        """部分接口缺失、部分有数据 → 仅缺失者告警."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "enable"},
            {"name": "Gi0/2"},  # missing
            {"name": "Gi0/3", "storm_control": "disable"},
        ]))
        assert len(results) == 2  # Gi0/2 missing, Gi0/3 disabled
        interfaces = {r.interface for r in results}
        assert interfaces == {"Gi0/2", "Gi0/3"}

    def test_config_defaults(self, rule):
        """未设 config 时应使用默认值 (required=True, strict=True)."""
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
        ]))
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL


# ══════════════════════════════════════════════════════════════
# 8. AlertRule 基类契约
# ══════════════════════════════════════════════════════════════

class TestAlertRuleContract:
    """验证 StormControlRule 符合 AlertRule 基类契约."""

    def test_class_vars(self):
        assert StormControlRule.name == "storm_control"
        assert StormControlRule.description == "风暴控制合规检查"

    def test_validate_passes(self, rule):
        errors = rule.validate()
        assert errors == []

    def test_returns_alert_result_list(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
        ]))
        assert isinstance(results, list)
        assert all(isinstance(r, AlertResult) for r in results)

    def test_result_has_rule_name(self, rule):
        results = rule.evaluate(_device([
            {"name": "Gi0/1", "storm_control": "disable"},
        ]))
        assert results[0].rule_name == "storm_control"
