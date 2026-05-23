import tomllib
from pathlib import Path

import pytest

from engine.plugin_base import PluginManifest
from engine.plugin_config import load_plugin_config, PluginConfig


# ── 测试 1: 合法 TOML 能正确解析为 PluginManifest ──────────────────────────

def test_load_valid_plugin_toml():
    """使用模板文件 plugin.example.toml 验证正确解析。"""
    example_path = Path(__file__).parents[1] / "templates" / "plugin.example.toml"

    manifest = load_plugin_config(str(example_path))

    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "optical_power_alert"
    assert manifest.version == "1.0.0"
    assert manifest.author == "netops team"
    assert manifest.description == "光模块接收功率异常检测"
    assert manifest.plugin_type == "alert"
    assert manifest.entry_point == "plugins.alerts.optical_power:OpticalPowerAlert"
    assert manifest.dependencies == []  # 模板无依赖
    assert "rx_power_warn_threshold" in manifest.config_schema
    assert "rx_power_crit_threshold" in manifest.config_schema


# ── 测试 2: 字段映射完整性 ─────────────────────────────────────────────────

def test_all_fields_map_correctly():
    """通过临时 TOML 验证所有字段均正确映射到 PluginManifest。"""
    toml_content = """
[plugin]
name = "test_plugin"
version = "2.0.0"
author = "tester"
description = "A test plugin"
type = "collector"
entry_point = "test.collector:Collector"

[plugin.dependencies]
dep_a = ">=1.0"
dep_b = ">=2.0"

[plugin.config]
timeout = {type = "integer", default = 30}
retries = {type = "integer", default = 3}
"""
    tmp = Path("/tmp/test_plugin_config_valid.toml")
    tmp.write_text(toml_content)

    try:
        manifest = load_plugin_config(str(tmp))
        assert manifest.name == "test_plugin"
        assert manifest.version == "2.0.0"
        assert manifest.author == "tester"
        assert manifest.description == "A test plugin"
        assert manifest.plugin_type == "collector"
        assert manifest.entry_point == "test.collector:Collector"
        assert sorted(manifest.dependencies) == ["dep_a", "dep_b"]
        assert "timeout" in manifest.config_schema
        assert "retries" in manifest.config_schema
    finally:
        tmp.unlink(missing_ok=True)


# ── 测试 3: 非法 TOML 抛异常 ──────────────────────────────────────────────

def test_invalid_toml_raises_exception():
    """非法的 TOML 文件应抛出 tomllib.TOMLDecodeError。"""
    invalid_content = b"this is [not valid toml = }"
    tmp = Path("/tmp/test_plugin_config_invalid.toml")
    tmp.write_bytes(invalid_content)

    try:
        with pytest.raises(tomllib.TOMLDecodeError):
            load_plugin_config(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


# ── 测试 4: PluginConfig dataclass 结构 ────────────────────────────────────

def test_plugin_config_dataclass():
    """验证 PluginConfig 包装器结构正确。"""
    manifest = PluginManifest(
        name="demo",
        version="1.0.0",
        author="tester",
        description="demo plugin",
        plugin_type="test",
    )
    config = PluginConfig(manifest=manifest, raw_config={"enabled": True})

    assert config.manifest is manifest
    assert config.raw_config == {"enabled": True}
    assert config.manifest.name == "demo"


# ── 测试 5: 缺少 name 字段抛出 KeyError ────────────────────────────────────

def test_missing_name_raises_keyerror():
    """缺少必需的 'name' 字段应抛出 KeyError。"""
    toml_content = b'[plugin]\nversion = "1.0"\n'
    tmp = Path("/tmp/test_plugin_config_missing_name.toml")
    tmp.write_bytes(toml_content)

    try:
        with pytest.raises(KeyError):
            load_plugin_config(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
