"""集成测试：告警规则引擎集成进 build_report()"""
import pytest
from engine.report import build_report, AlertItem, DeviceSummary, Report


def _make_iface(ip="192.168.1.1", name="GigabitEthernet 0/1",
                status="up", rx_power=None, errors=None,
                storm_control="yes", **kw):
    row = {
        "_device_ip": ip,
        "_device_name": "switch-1",
        "interface": name,
        "status": status,
    }
    if rx_power is not None:
        row["ddm_rx_power"] = str(rx_power)
        row["RX 光功率(dBm)"] = str(rx_power)
    if errors:
        for k, v in errors.items():
            row[k] = str(v)
    if storm_control is not None:
        row["storm_control"] = storm_control
    row.update(kw)
    return row


class TestBuildReportPluginAlerts:
    """验证 build_report() 包含插件告警结果"""

    def test_plugin_alerts_in_report(self):
        ifaces = [_make_iface(rx_power=-25.0)]
        report = build_report(ifaces)
        rule_names = {a.rule_name for a in report.alerts}
        assert "optics_power" in rule_names

    def test_plugin_and_legacy_alerts_coexist(self):
        ifaces = [_make_iface(rx_power=-25.0)]
        report = build_report(ifaces)
        legacy = [a for a in report.alerts if not a.rule_name]
        plugin = [a for a in report.alerts if a.rule_name]
        assert any("光功率" in a.message for a in legacy)
        assert any(a.rule_name == "optics_power" for a in plugin)

    def test_no_false_alerts_healthy(self):
        ifaces = [_make_iface(rx_power=-10.0)]
        report = build_report(ifaces)
        has_optical = any("光功率" in a.message or a.rule_name == "optics_power"
                          for a in report.alerts)
        assert not has_optical

    def test_plugin_category_mapping(self):
        ifaces = [_make_iface(rx_power=-25.0)]
        report = build_report(ifaces)
        optics_alerts = [a for a in report.alerts if a.rule_name == "optics_power"]
        if optics_alerts:
            assert optics_alerts[0].category == "optical"

    def test_engine_error_graceful(self, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("engine crash")
        monkeypatch.setattr(
            "engine.report._get_alert_engine", broken)
        ifaces = [_make_iface(rx_power=-25.0)]
        report = build_report(ifaces)
        errors = [a for a in report.alerts if a.rule_name == "_engine_error"]
        assert len(errors) > 0
        assert "异常" in errors[0].message or "crash" in errors[0].message


class TestAlertItemRuleName:
    """验证 AlertItem 新增 rule_name 字段"""

    def test_rule_name_default_empty(self):
        item = AlertItem(
            device_ip="1.1.1.1", device_name="sw",
            category="optical", severity="warning",
            message="test",
        )
        assert item.rule_name == ""

    def test_rule_name_settable(self):
        item = AlertItem(
            device_ip="1.1.1.1", device_name="sw",
            category="optical", severity="warning",
            message="test", rule_name="optics_power",
        )
        assert item.rule_name == "optics_power"
