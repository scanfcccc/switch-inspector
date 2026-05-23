import logging
import os
import tempfile
import time

import pytest

from engine.hot_reload import auto_start, auto_stop, _reload_rules

logging.basicConfig(level=logging.DEBUG)


class TestAutoStartStop:
    def test_start_stop_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            obs = auto_start(watch_path=d)
            assert obs is not None
            time.sleep(0.3)
            auto_stop()
        assert True

    def test_start_twice_returns_same(self):
        with tempfile.TemporaryDirectory() as d:
            o1 = auto_start(watch_path=d)
            o2 = auto_start(watch_path=d)
            assert o1 is o2
            auto_stop()

    def test_nonexistent_dir_returns_none(self):
        obs = auto_start(watch_path="/tmp/_nonexistent_dir_xyz")
        assert obs is None
        auto_stop()

    def test_stop_no_observer(self):
        auto_stop()
        assert True


class TestReloadRules:
    def test_reload_on_empty_mgr_does_not_crash(self, monkeypatch):
        class FakeMgr:
            _rules = {}
            _enabled = {}
            _config = {}
            def discover_rules(self): return 0
            def configure_rule(self, r, c): pass
        monkeypatch.setattr("engine.hot_reload._get_alert_mgr", lambda: FakeMgr())
        _reload_rules()
        assert True

    def test_reload_crash_logged(self, monkeypatch, caplog):
        def broken():
            raise RuntimeError("simulated")
        monkeypatch.setattr("engine.hot_reload._get_alert_mgr", broken)
        with caplog.at_level(logging.ERROR):
            _reload_rules()
        assert "simulated" in caplog.text
