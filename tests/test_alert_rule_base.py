import pytest
from engine.alert_rule_base import AlertSeverity, AlertResult, AlertRule


class TestAlertSeverity:
    """AlertSeverity 枚举值和排序."""

    def test_values(self):
        """成员应有正确的整数值（数值越大越严重）."""
        assert AlertSeverity.INFO.value == 1
        assert AlertSeverity.WARNING.value == 2
        assert AlertSeverity.CRITICAL.value == 3

    def test_ordering(self):
        """严重等级的顺序应为 INFO < WARNING < CRITICAL."""
        assert AlertSeverity.INFO.value < AlertSeverity.WARNING.value
        assert AlertSeverity.WARNING.value < AlertSeverity.CRITICAL.value

    def test_membership(self):
        """三个成员应唯一且完整."""
        members = set(AlertSeverity)
        assert members == {AlertSeverity.INFO, AlertSeverity.WARNING,
                           AlertSeverity.CRITICAL}


class TestAlertResult:
    """AlertResult 数据类构造."""

    def test_all_fields(self):
        """所有字段均传入时应正确存储."""
        details = {"rx_power": -18.5, "threshold": -15.0}
        result = AlertResult(
            rule_name="optics_power_warning",
            severity=AlertSeverity.WARNING,
            message="接口光功率异常",
            device_ip="10.0.0.1",
            interface="Gi0/1",
            details=details,
        )
        assert result.rule_name == "optics_power_warning"
        assert result.severity == AlertSeverity.WARNING
        assert result.message == "接口光功率异常"
        assert result.device_ip == "10.0.0.1"
        assert result.interface == "Gi0/1"
        assert result.details == details

    def test_defaults(self):
        """可选字段应默认为 None."""
        result = AlertResult(
            rule_name="test_rule",
            severity=AlertSeverity.INFO,
            message="测试告警",
        )
        assert result.device_ip is None
        assert result.interface is None
        assert result.details is None


class TestAlertRuleABC:
    """AlertRule 抽象基类行为."""

    def test_cannot_instantiate_directly(self):
        """直接实例化 AlertRule 应抛出 TypeError."""
        with pytest.raises(TypeError):
            AlertRule()  # type: ignore

    def test_must_implement_evaluate(self):
        """未实现 evaluate() 的子类应抛出 TypeError."""
        with pytest.raises(TypeError):

            class MissingEvaluate(AlertRule):  # type: ignore
                name = "no_eval"
                description = "缺少 evaluate 的子类"

            # 此时 Python 并不会报错，因为抽象方法要到实例化时才检查
            # 但我们需要给一个默认 severity 以避免 validate 干扰
            # 实际上 Python 在类定义完成时就会检查抽象方法
            # 如果在类体结束时仍有未实现的抽象方法，实例化时报错
            instance = MissingEvaluate()  # 应该抛出 TypeError

    def test_subclass_without_name_fails_validate(self):
        """未定义 name 的子类在 validate() 时应返回错误."""
        class NoName(AlertRule):
            description = "缺少 name 的告警规则"

            def evaluate(self, device_data):
                return []

        rule = NoName()
        errors = rule.validate()
        assert any("name" in e for e in errors)

    def test_subclass_without_description_fails_validate(self):
        """未定义 description 的子类在 validate() 时应返回错误."""
        class NoDesc(AlertRule):
            name = "no_desc_rule"

            def evaluate(self, device_data):
                return []

        rule = NoDesc()
        errors = rule.validate()
        assert any("description" in e for e in errors)

    def test_concrete_rule_returns_expected_shape(self):
        """完整的 AlertRule 子类应返回符合预期的 AlertResult."""
        class OpticsPowerRule(AlertRule):
            name = "optics_power_warning"
            description = "光功率异常告警"

            def evaluate(self, device_data):
                return [
                    AlertResult(
                        rule_name=self.name,
                        severity=self.severity,
                        message="接口 Gi0/1 光功率异常 (RX: -18.5 dBm)",
                        device_ip=device_data.get("device_ip"),
                        interface="Gi0/1",
                        details={"rx_power": -18.5, "threshold": -15.0},
                    ),
                ]

        rule = OpticsPowerRule()
        device_data = {
            "device_ip": "10.0.0.1",
            "device_name": "switch-01",
            "interfaces": [
                {"name": "Gi0/1", "ddm_rx_power": "-18.5"},
            ],
        }
        results = rule.evaluate(device_data)

        assert len(results) == 1
        result = results[0]

        assert result.rule_name == "optics_power_warning"
        assert result.severity == AlertSeverity.WARNING
        assert result.message == "接口 Gi0/1 光功率异常 (RX: -18.5 dBm)"
        assert result.device_ip == "10.0.0.1"
        assert result.interface == "Gi0/1"
        assert result.details == {"rx_power": -18.5, "threshold": -15.0}

    def test_default_severity_is_warning(self):
        """未覆盖 severity 的子类应默认使用 WARNING."""
        class DefaultRule(AlertRule):
            name = "default_severity"
            description = "测试默认严重等级"

            def evaluate(self, device_data):
                return [
                    AlertResult(
                        rule_name=self.name,
                        severity=self.severity,
                        message="默认等级告警",
                    ),
                ]

        rule = DefaultRule()
        assert rule.severity == AlertSeverity.WARNING

        results = rule.evaluate({})
        assert results[0].severity == AlertSeverity.WARNING

    def test_no_auto_register_flag(self):
        """AlertRule 应设置 no_auto_register = True 避免被注册为解析器插件."""
        assert AlertRule.no_auto_register is True
