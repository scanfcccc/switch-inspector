"""告警规则引擎 — 加载、配置、执行告警规则插件。"""

import importlib
import inspect
import os
import pkgutil
import sys
from typing import Dict, List, Optional, Any

import yaml

from engine.alert_rule_base import AlertRule, AlertResult


class AlertPluginManager:
    """告警规则插件管理器。

    负责:
      1. 从 ``rules/`` 包中发现 :class:`AlertRule` 子类
      2. 从 YAML 文件加载规则配置
      3. 对所有已发现且启用的规则执行评估并聚合结果

    Usage::

        mgr = AlertPluginManager(rules_dir="rules")
        count = mgr.discover_rules()               # 发现 4 条规则
        mgr.load_config("rules/rules.yaml")         # 加载 YAML 配置
        result = mgr.evaluate_all(device_data)      # 执行所有规则
        alerts = mgr.get_alerts(device_data)        # 便捷调用
    """

    def __init__(
        self,
        rules_dir: str = "rules",
        config_path: Optional[str] = None,
    ):
        """
        Args:
            rules_dir: 规则包目录（相对于当前工作目录，或绝对路径）。
            config_path: 可选 YAML 配置文件的路径。如果提供，立即加载。
        """
        self._rules_dir = os.path.abspath(rules_dir)
        self._rules: Dict[str, AlertRule] = {}
        self._enabled: Dict[str, bool] = {}
        self._config: Dict[str, Any] = {}

        if config_path is not None:
            self.load_config(config_path)

    # ── 规则发现 ──────────────────────────────────────────────────────

    def discover_rules(self) -> int:
        """扫描 ``rules/`` 目录，发现所有 :class:`AlertRule` 子类。

        使用 :func:`pkgutil.iter_modules` 遍历目录，导入每个模块，
        然后通过 :func:`inspect.getmembers` 查找 ``AlertRule`` 的子类。
        自动跳过 ``AlertRule`` 基类本身以及 ``_`` 前缀的内部模块。

        Returns:
            发现的规则数量。
        """
        count = 0
        rules_path = self._rules_dir
        parent = os.path.dirname(rules_path)
        pkg_name = os.path.basename(rules_path)

        # 确保父目录在 sys.path 中，以便使用 package.module 形式导入
        path_added = False
        if parent and parent not in sys.path:
            sys.path.insert(0, parent)
            path_added = True

        try:
            for _importer, modname, _ispkg in pkgutil.iter_modules([rules_path]):
                if modname.startswith("_"):
                    continue
                full_modname = f"{pkg_name}.{modname}"
                module = importlib.import_module(full_modname)
                for _name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, AlertRule)
                        and obj is not AlertRule
                    ):
                        instance: AlertRule = obj()
                        self._rules[instance.name] = instance
                        self._enabled[instance.name] = True
                        count += 1
        finally:
            if path_added:
                try:
                    sys.path.remove(parent)
                except ValueError:
                    pass

        return count

    # ── 配置加载 ──────────────────────────────────────────────────────

    def load_config(self, path: str) -> dict:
        """从 YAML 文件加载规则配置。

        预期的 YAML 结构::

            rules:
              optics_power:
                enabled: true
                warn_threshold: -15.0
                ...

        Args:
            path: YAML 配置文件路径。

        Returns:
            ``rules`` 键下的配置字典，按规则名索引。
        """
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._config = (raw.get("rules", {}) if isinstance(raw, dict) else {})
        return self._config

    # ── 规则配置 ──────────────────────────────────────────────────────

    def configure_rule(self, rule: AlertRule, config: dict) -> AlertRule:
        """对单条规则实例应用配置。

        从配置中提取 ``enabled`` 标志并内部记录，其余字段
        直接赋值为 ``rule.config``。

        Args:
            rule:  待配置的规则实例。
            config: 该规则的配置字典（包含 ``enabled`` 以及各阈值等）。

        Returns:
            配置后的规则实例。
        """
        enabled = config.get("enabled", True)
        self._enabled[rule.name] = bool(enabled)
        rule.config = {k: v for k, v in config.items() if k != "enabled"}
        return rule

    # ── 规则执行 ──────────────────────────────────────────────────────

    def evaluate_all(self, device_data: dict) -> dict:
        """对所有已发现且启用的规则执行一次评估。

        每条规则在独立的 ``try/except`` 中运行。任一条规则崩溃
        不影响其它规则，错误信息被收集到 ``errors`` 列表中。

        Args:
            device_data: 设备数据字典，包含
                ``device_ip``, ``device_name``, ``interfaces`` 等字段。

        Returns:
            {
                "alerts": List[AlertResult],   # 所有非空结果
                "stats": {
                    "rules_total": int,          # 发现的总规则数
                    "rules_enabled": int,        # 启用的规则数
                    "alerts_by_rule": {           # 各规则产生的告警数
                        rule_name: count, ...
                    },
                    "alerts_by_severity": {       # 各严重等级的告警数
                        severity_name: count, ...
                    },
                },
                "errors": List[str],             # 规则运行中出现的错误
            }
        """
        alerts: List[AlertResult] = []
        errors: List[str] = []
        stats: Dict[str, Any] = {
            "rules_total": 0,
            "rules_enabled": 0,
            "alerts_by_rule": {},
            "alerts_by_severity": {},
        }

        for rule_name, rule in self._rules.items():
            stats["rules_total"] += 1

            enabled = self._enabled.get(rule_name, True)
            if not enabled:
                continue

            stats["rules_enabled"] += 1

            try:
                results = rule.evaluate(device_data)
                if results:
                    stats["alerts_by_rule"][rule_name] = len(results)
                    for r in results:
                        sev = r.severity.name
                        stats["alerts_by_severity"][sev] = (
                            stats["alerts_by_severity"].get(sev, 0) + 1
                        )
                    alerts.extend(results)
            except Exception as e:
                errors.append(f"{rule_name}: {e}")

        return {
            "alerts": alerts,
            "stats": stats,
            "errors": errors,
        }

    def get_alerts(self, device_data: dict) -> List[AlertResult]:
        """便捷方法：运行 :meth:`evaluate_all` 并仅返回告警列表。"""
        return self.evaluate_all(device_data)["alerts"]
