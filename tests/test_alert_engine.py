"""Test suite for AlertPluginManager — rule discovery, config, execution."""

from pathlib import Path
from typing import List

import pytest
import yaml

from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity
from engine.alert_engine import AlertPluginManager


# ── helpers ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEVICE_DATA = {
    "device_ip": "10.0.0.1",
    "device_name": "switch-01",
    "interfaces": [
        {
            "name": "Gi0/1",
            # Optics: rx_power = -25.0 < crit(-20.0)  → CRITICAL
            "ddm_rx_power": "-25.0",
            "ddm_tx_power": "-5.0",
            "ddm_temperature": "45.0",
            # Errors: 500 > 100 → WARNING
            "errors_in": 500,
            "crc_errors": 200,
            # Storm: enabled → skip
            "storm_control": "enable",
        },
        {
            "name": "Gi0/2",
            # Optics: rx_power = -18.0 < warn(-15.0)  → WARNING
            "ddm_rx_power": "-18.0",
            # Errors: 50 < 100 → no alert
            "errors_in": 50,
            # Storm: disabled → CRITICAL
            "storm_control": "disable",
        },
        {
            "name": "Gi0/3",
            # No DDM data, no error counters, no storm control → CRITICAL
        },
    ],
    # System health — all healthy
    "fan_1_status": "normal",
    "fan_1_speed": "4500",
    "temperature": "55",
    "power_supply_1": "normal",
}


@pytest.fixture
def mgr():
    """AlertPluginManager with rules discovered (no config loaded)."""
    m = AlertPluginManager(rules_dir=str(PROJECT_ROOT / "rules"))
    m.discover_rules()
    return m


# ── tests ────────────────────────────────────────────────────────────────


class TestDiscoverRules:
    """discover_rules()"""

    def test_discover_rules_finds_all_4(self):
        """扫描 rules/ 包应发现全部 4 条规则。"""
        m = AlertPluginManager(rules_dir=str(PROJECT_ROOT / "rules"))
        count = m.discover_rules()
        assert count == 4, f"Expected 4 rules, got {count}"

        names = set(m._rules.keys())
        expected = {"optics_power", "interface_errors", "storm_control",
                     "system_health"}
        assert names == expected, f"Missing: {expected - names}"

        # 所有规则默认启用
        assert all(m._enabled.values())


class TestLoadConfig:
    """load_config()"""

    def test_load_config_parses_yaml(self, tmp_path):
        """YAML 解析应返回正确的嵌套结构。"""
        cfg = tmp_path / "rules.yaml"
        cfg.write_text("""\
rules:
  optics_power:
    enabled: true
    warn_threshold: -12.0
    crit_threshold: -18.0
  interface_errors:
    enabled: true
    max_errors: 250
  storm_control:
    enabled: false
    required: true
    strict: true
  system_health:
    enabled: true
    max_temp: 65
    checks:
      - fan
      - temperature
""")
        m = AlertPluginManager()
        config = m.load_config(str(cfg))

        assert "optics_power" in config
        assert config["optics_power"]["warn_threshold"] == -12.0
        assert config["optics_power"]["crit_threshold"] == -18.0
        assert config["interface_errors"]["max_errors"] == 250
        assert config["storm_control"]["enabled"] is False
        assert config["system_health"]["max_temp"] == 65
        assert config["system_health"]["checks"] == ["fan", "temperature"]

    def test_load_config_empty_file(self, tmp_path):
        """空 YAML 文件应返回空字典。"""
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("")
        m = AlertPluginManager()
        config = m.load_config(str(cfg))
        assert config == {}

    def test_load_config_no_rules_key(self, tmp_path):
        """YAML 无 rules 键时应返回空字典。"""
        cfg = tmp_path / "no_rules.yaml"
        cfg.write_text("other_key: 42")
        m = AlertPluginManager()
        config = m.load_config(str(cfg))
        assert config == {}


class TestConfigureRule:
    """configure_rule()"""

    def test_configure_rule_applies_config(self):
        """配置应正确写入 rule.config 并记录 enabled 状态。"""
        class DummyRule(AlertRule):
            name = "dummy"
            description = "test rule"

            def evaluate(self, device_data):
                return []

        rule = DummyRule()
        m = AlertPluginManager()
        cfg = {"enabled": True, "max_errors": 200, "custom_flag": "xyz"}
        m.configure_rule(rule, cfg)

        assert rule.config == {"max_errors": 200, "custom_flag": "xyz"}
        assert m._enabled["dummy"] is True

    def test_configure_rule_disabled(self):
        """enabled: false 应正确存储。"""
        class DummyRule(AlertRule):
            name = "dummy_disabled"
            description = "test disabled"

            def evaluate(self, device_data):
                return [AlertResult(rule_name=self.name,
                                    severity=AlertSeverity.WARNING,
                                    message="should not appear")]

        rule = DummyRule()
        m = AlertPluginManager()
        m._rules["dummy_disabled"] = rule

        m.configure_rule(rule, {"enabled": False})
        assert m._enabled["dummy_disabled"] is False

        # 禁用后 evaluate_all 不应包含此规则的告警
        result = m.evaluate_all(DEVICE_DATA)
        names = {a.rule_name for a in result["alerts"]}
        assert "dummy_disabled" not in names


class TestEvaluateAll:
    """evaluate_all()"""

    def test_enabled_rules_produce_alerts(self, mgr):
        """启用的规则应针对异常设备数据产生告警。"""
        result = mgr.evaluate_all(DEVICE_DATA)
        alert_names = {a.rule_name for a in result["alerts"]}

        # optics_power: Gi0/1 CRITICAL + Gi0/2 WARNING
        assert "optics_power" in alert_names
        # interface_errors: Gi0/1 WARNING
        assert "interface_errors" in alert_names
        # storm_control: Gi0/2 CRITICAL + Gi0/3 CRITICAL
        assert "storm_control" in alert_names

    def test_disabled_rule_produces_no_alerts(self, mgr):
        """enabled: false 的规则应完全跳过。"""
        mgr._enabled["optics_power"] = False
        result = mgr.evaluate_all(DEVICE_DATA)
        for alert in result["alerts"]:
            assert alert.rule_name != "optics_power"

    def test_evaluate_all_stats_shape(self, mgr):
        """evaluate_all 返回的 stats 应包含正确形状和数值。"""
        result = mgr.evaluate_all(DEVICE_DATA)
        stats = result["stats"]

        assert stats["rules_total"] == 4
        assert stats["rules_enabled"] == 4

        # optics_power: 2 alerts (Gi0/1 CRITICAL, Gi0/2 WARNING)
        assert stats["alerts_by_rule"]["optics_power"] == 2
        # interface_errors: 1 alert (Gi0/1 WARNING)
        assert stats["alerts_by_rule"]["interface_errors"] == 1
        # storm_control: 2 alerts (Gi0/2 CRITICAL, Gi0/3 CRITICAL)
        assert stats["alerts_by_rule"]["storm_control"] == 2

        # CRITICAL: optics_power(1) + storm_control(2) = 3
        assert stats["alerts_by_severity"]["CRITICAL"] == 3
        # WARNING: optics_power(1) + interface_errors(1) = 2
        assert stats["alerts_by_severity"]["WARNING"] == 2

        assert result["errors"] == []

    def test_rule_crash_does_not_affect_others(self, mgr):
        """单条规则崩溃不应阻止其他规则执行。"""
        # 注入一条总是崩溃的规则
        class CrashRule(AlertRule):
            name = "crash_test"
            description = "intentionally crashes"

            def evaluate(self, device_data):
                raise RuntimeError("Intentional crash for testing")

        mgr._rules["crash_test"] = CrashRule()
        mgr._enabled["crash_test"] = True

        result = mgr.evaluate_all(DEVICE_DATA)

        # 其他规则仍然产生告警
        assert len(result["alerts"]) >= 3

        # 崩溃规则被记录在 errors 中
        assert any("crash_test" in e for e in result["errors"])
        assert any("Intentional crash" in e for e in result["errors"])

        # stats 包含崩溃规则
        assert result["stats"]["rules_total"] == 5
        assert result["stats"]["rules_enabled"] == 5
        # crash 不出现在 alerts_by_rule 中
        assert "crash_test" not in result["stats"]["alerts_by_rule"]

    def test_evaluate_all_no_config_uses_defaults(self, mgr):
        """未加载配置时规则应使用默认配置运行。"""
        # mgr fixture 没有调用 load_config，规则使用默认 config
        result = mgr.evaluate_all(DEVICE_DATA)

        # 有告警产生（默认阈值生效）
        assert len(result["alerts"]) > 0
        # 无错误
        assert result["errors"] == []
        # 所有规则均启用
        assert result["stats"]["rules_enabled"] == 4


class TestGetAlerts:
    """get_alerts() — 便捷方法"""

    def test_get_alerts_returns_list(self, mgr):
        """get_alerts 应直接返回 AlertResult 列表。"""
        alerts = mgr.get_alerts(DEVICE_DATA)
        assert isinstance(alerts, list)
        if alerts:
            assert isinstance(alerts[0], AlertResult)

    def test_get_alerts_matches_evaluate_all(self, mgr):
        """get_alerts 的结果应与 evaluate_all['alerts'] 一致。"""
        full = mgr.evaluate_all(DEVICE_DATA)
        short = mgr.get_alerts(DEVICE_DATA)
        assert len(short) == len(full["alerts"])
        for s, f in zip(short, full["alerts"]):
            assert s.rule_name == f.rule_name
            assert s.severity == f.severity


class TestConfigIntegration:
    """配置 → 规则的全链路集成。"""

    def test_configure_then_evaluate(self, mgr, tmp_path):
        """通过 YAML 配置后执行评估。"""
        # 用 YAML 修改阈值
        cfg = tmp_path / "rules.yaml"
        cfg.write_text("""\
rules:
  optics_power:
    enabled: true
    warn: -30.0    # 非常宽松 → 不会产生 WARNING
    crit: -40.0    # 非常宽松 → 不会产生 CRITICAL
  interface_errors:
    enabled: true
    max_errors: 1000         # 宽松 → 不会产生告警
  storm_control:
    enabled: false           # 禁用
  system_health:
    enabled: true
    max_temp: 60
    checks:
      - temperature
""")
        mgr.load_config(str(cfg))

        # 将 YAML 配置应用到每条已发现的规则
        for rule_name, rule in list(mgr._rules.items()):
            if rule_name in mgr._config:
                mgr.configure_rule(rule, mgr._config[rule_name])

        result = mgr.evaluate_all(DEVICE_DATA)

        # optics_power: 阈值非常宽松，-25.0 > -40.0，-18.0 > -30.0 → 无告警
        # interface_errors: max_errors=1000, 500 < 1000 → 无告警
        # storm_control: disabled → 跳过
        # system_health: 只有 temperature 检查，55 < 60 → 无告警
        alert_names = {a.rule_name for a in result["alerts"]}
        assert "optics_power" not in alert_names
        assert "interface_errors" not in alert_names
        assert "storm_control" not in alert_names
        assert len(result["alerts"]) == 0

        # 确认 disabled 规则被正确记录
        assert mgr._enabled["storm_control"] is False
        assert result["stats"]["rules_enabled"] == 3  # 4 total - 1 disabled
        assert result["stats"]["rules_total"] == 4
