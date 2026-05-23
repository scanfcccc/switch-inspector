import pytest
from engine.plugin_base import PluginManifest, PluginBase
from engine.plugin_exceptions import (
    PluginValidationError,
    PluginLoadError,
    PluginRuntimeError,
)


class TestPluginManifest:
    """PluginManifest dataclass field completeness."""

    def test_all_fields_present(self):
        """创建实例后检查所有8个字段"""
        m = PluginManifest(
            name="test",
            version="1.0.0",
            author="me",
            description="desc",
            plugin_type="parser",
            dependencies=["dep1"],
            config_schema={"key": "str"},
            entry_point="main",
        )
        assert m.name == "test"
        assert m.version == "1.0.0"
        assert m.author == "me"
        assert m.description == "desc"
        assert m.plugin_type == "parser"
        assert m.dependencies == ["dep1"]
        assert m.config_schema == {"key": "str"}
        assert m.entry_point == "main"

    def test_default_values(self):
        """没有提供的字段应有合理的默认值"""
        m = PluginManifest(
            name="minimal",
            version="0.1",
            author="a",
            description="d",
            plugin_type="t",
        )
        assert m.dependencies == []
        assert m.config_schema == {}
        assert m.entry_point == ""


class TestPluginBaseABC:
    """PluginBase 抽象基类行为."""

    def test_cannot_instantiate_directly(self):
        """直接实例化 PluginBase 应抛出 TypeError"""
        with pytest.raises(TypeError):
            PluginBase()  # type: ignore

    def test_valid_subclass_can_instantiate(self):
        """合法子类（实现所有抽象方法）应能正常实例化"""
        class GoodPlugin(PluginBase):
            manifest = PluginManifest(
                name="good",
                version="1.0",
                author="me",
                description="a good plugin",
                plugin_type="parser",
            )

            def validate(self) -> list:
                return []

        p = GoodPlugin()
        assert isinstance(p, PluginBase)
        assert p.manifest.name == "good"

    def test_validate_default_returns_empty_list(self):
        """validate() 默认实现（super()）应返回 []"""
        class Plugin(PluginBase):
            manifest = PluginManifest(
                name="p", version="1", author="a",
                description="d", plugin_type="t",
            )

            def validate(self) -> list:
                return super().validate()

        p = Plugin()
        assert p.validate() == []

    def test_validate_override_returns_errors(self):
        """子类覆盖 validate() 可返回校验错误列表"""
        class FailingPlugin(PluginBase):
            manifest = PluginManifest(
                name="fail", version="1", author="a",
                description="d", plugin_type="t",
            )

            def validate(self) -> list:
                return ["missing dependency: foo", "invalid version format"]

        p = FailingPlugin()
        errors = p.validate()
        assert len(errors) == 2
        assert "missing dependency: foo" in errors
        assert "invalid version format" in errors

    def test_on_load_on_unload_default_noop(self):
        """on_load() / on_unload() 默认空实现不应抛异常"""
        class SilentPlugin(PluginBase):
            manifest = PluginManifest(
                name="silent", version="1", author="a",
                description="d", plugin_type="t",
            )

            def validate(self) -> list:
                return []

        p = SilentPlugin()
        # 调用空实现不应抛出任何异常
        p.on_load()
        p.on_unload()


class TestPluginExceptions:
    """异常类应正确实例化并可被捕获."""

    def test_plugin_validation_error(self):
        with pytest.raises(PluginValidationError):
            raise PluginValidationError("invalid config")

    def test_plugin_load_error(self):
        with pytest.raises(PluginLoadError):
            raise PluginLoadError("module not found")

    def test_plugin_runtime_error(self):
        with pytest.raises(PluginRuntimeError):
            raise PluginRuntimeError("execution failed")

    def test_exceptions_inherit_from_exception(self):
        assert issubclass(PluginValidationError, Exception)
        assert issubclass(PluginLoadError, Exception)
        assert issubclass(PluginRuntimeError, Exception)
