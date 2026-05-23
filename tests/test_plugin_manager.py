import pytest
from dataclasses import dataclass
from typing import List
from engine.plugin_base import PluginBase, PluginManifest
from engine.plugin_exceptions import PluginValidationError
from engine.plugin_manager import PluginManager, get_plugin_manager


# ── helpers ──────────────────────────────────────────────────────────────

# Reset singleton so each test gets a fresh PluginManager
@pytest.fixture(autouse=True)
def _reset_manager():
    import engine.plugin_manager as pm

    pm._INSTANCE = None
    yield


def make_plugin(
    name: str = "test",
    plugin_type: str = "parser",
    version: str = "1.0.0",
    author: str = "tester",
    description: str = "test plugin",
    dependencies: List[str] = None,
    valid: bool = True,
    method_side_effect: dict = None,
):
    _manifest = PluginManifest(
        name=name,
        version=version,
        author=author,
        description=description,
        plugin_type=plugin_type,
        dependencies=dependencies or [],
    )

    def _validate(self) -> List[str]:
        return [] if valid else ["mock validation error"]

    def _run(self, x=None):
        if method_side_effect and "run" in method_side_effect:
            raise method_side_effect["run"]
        return f"{name}-result"

    _P = type(
        "_P",
        (PluginBase,),
        {
            "manifest": _manifest,
            "validate": _validate,
            "run": _run,
            "on_unload": lambda self: None,
        },
    )
    return _P()


# ── tests ────────────────────────────────────────────────────────────────


class TestPluginManager:
    def test_register_and_get_plugin(self):
        """注册后 get_plugin() 返回正确实例"""
        mgr = PluginManager()
        p = make_plugin(name="alpha")
        mgr.register(p)
        assert mgr.get_plugin("alpha") is p

    def test_get_plugins_by_type(self):
        """按 plugin_type 过滤插件"""
        mgr = PluginManager()
        p1 = make_plugin(name="a", plugin_type="parser")
        p2 = make_plugin(name="b", plugin_type="parser")
        p3 = make_plugin(name="c", plugin_type="formatter")
        mgr.register(p1)
        mgr.register(p2)
        mgr.register(p3)

        parsers = mgr.get_plugins("parser")
        assert len(parsers) == 2
        assert p1 in parsers
        assert p2 in parsers
        assert p3 not in parsers

    def test_register_validation_failure(self):
        """validate() 失败的插件拒绝注册，抛 PluginValidationError"""
        mgr = PluginManager()
        p = make_plugin(name="bad", valid=False)
        with pytest.raises(PluginValidationError, match="bad"):
            mgr.register(p)
        assert mgr.get_plugin("bad") is None

    def test_get_plugin_nonexistent(self):
        """未注册的插件返回 None"""
        mgr = PluginManager()
        assert mgr.get_plugin("nope") is None

    def test_execute_isolation(self):
        """execute() 隔离异常 — 1 个崩不影响另外 2 个"""
        mgr = PluginManager()
        p_ok1 = make_plugin(name="ok1", plugin_type="parser")
        p_bad = make_plugin(
            name="bad",
            plugin_type="parser",
            method_side_effect={"run": ValueError("boom")},
        )
        p_ok2 = make_plugin(name="ok2", plugin_type="parser")
        for p in (p_ok1, p_bad, p_ok2):
            mgr.register(p)

        results = mgr.execute("parser", "run")
        assert results[0] == "ok1-result"
        assert results[1] is None  # 异常插件返回 None
        assert results[2] == "ok2-result"

    def test_topological_order(self):
        """拓扑排序 — B 依赖 A，结果中 A 在 B 前"""
        mgr = PluginManager()
        p_a = make_plugin(name="A", dependencies=[])
        p_b = make_plugin(name="B", dependencies=["A"])
        mgr.register(p_a)
        mgr.register(p_b)

        ordered = mgr.topological_order(mgr.get_plugins("parser"))
        names = [p.manifest.name for p in ordered]
        assert names.index("A") < names.index("B")

    def test_load_all_and_counts(self, tmp_path, monkeypatch):
        """load_all 扫描目录并返回正确计数"""
        mgr = PluginManager()

        p1_dir = tmp_path / "p1"
        p1_dir.mkdir()
        (p1_dir / "plug_alpha.py").write_text(
            """
from engine.plugin_base import PluginBase, PluginManifest
from typing import List

_mft = PluginManifest(name="alpha", version="1.0", author="t", description="d", plugin_type="scanner")

class AlphaPlugin(PluginBase):
    manifest = _mft
    def validate(self) -> List[str]:
        return []
"""
        )

        p2_dir = tmp_path / "p2"
        p2_dir.mkdir()
        (p2_dir / "plug_beta.py").write_text(
            """
from engine.plugin_base import PluginBase, PluginManifest
from typing import List

_mft = PluginManifest(name="beta", version="1.0", author="t", description="d", plugin_type="scanner")

class BetaPlugin(PluginBase):
    manifest = _mft
    def validate(self) -> List[str]:
        return []
"""
        )

        monkeypatch.syspath_prepend(str(p1_dir))
        monkeypatch.syspath_prepend(str(p2_dir))

        counts = mgr.load_all([str(p1_dir), str(p2_dir)])
        assert counts.get("scanner", 0) == 2
        assert mgr.get_plugin("alpha") is not None
        assert mgr.get_plugin("beta") is not None

    def test_get_plugin_manager_singleton(self):
        """get_plugin_manager() 返回同一个实例"""
        m1 = get_plugin_manager()
        m2 = get_plugin_manager()
        assert m1 is m2

    def test_unload_all(self):
        """unload_all 清空注册表"""
        mgr = PluginManager()
        p = make_plugin(name="x")
        mgr.register(p)
        assert mgr.get_plugin("x") is not None
        mgr.unload_all()
        assert mgr.get_plugin("x") is None
