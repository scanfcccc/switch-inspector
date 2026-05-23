# Switch Inspector 插件开发规范

## 1. 概述

Switch Inspector 的插件系统支持两种插件类型：**解析器（parser）** 和 **告警规则（alert rule）**。插件通过 `PluginBase` 抽象基类统一接口，由 `PluginManager` 统一管理生命周期。

## 2. 插件生命周期

```
加载 → 校验(validate) → 注册(register) → 执行(execute) → 卸载(on_unload)
```

- **加载**: `discover()` 扫描目录，`importlib` 导入模块
- **校验**: 调用 `validate()`，返回错误列表；非空则抛出 `PluginValidationError`，跳过注册
- **注册**: 按 `plugin_type` 分组存入 `_registry[type][name]`
- **执行**: `execute()` 遍历指定类型插件，调用目标方法，单条失败不影响其他
- **卸载**: `unload_all()` 调用每个插件的 `on_unload()`，清空注册表

## 3. PluginBase API

```python
# engine/plugin_base.py
@dataclass
class PluginManifest:
    name: str
    version: str
    author: str
    description: str
    plugin_type: str          # "parser" | "alert"
    dependencies: list[str]   # 依赖的插件名列表
    config_schema: dict       # JSON Schema 格式的配置声明
    entry_point: str          # "module.path:ClassName"

class PluginBase(ABC):
    manifest: ClassVar[PluginManifest]

    @abstractmethod
    def validate(self) -> list[str]: ...   # 返回空列表 = 校验通过
    def on_load(self): ...                 # 加载后回调
    def on_unload(self): ...               # 卸载前回调
```

## 4. plugin.toml 清单

```toml
# templates/plugin.example.toml
[plugin]
name = "optical_power_alert"
version = "1.0.0"
author = "netops team"
description = "光模块接收功率异常检测"
type = "alert"
entry_point = "plugins.alerts.optical_power:OpticalPowerAlert"

[plugin.dependencies]
# 依赖的插件名列表（可选）

[plugin.config]
# JSON Schema 格式的配置声明
rx_power_warn_threshold = {type = "number", default = -15.0, description = "RX power warning threshold (dBm)"}
```

`load_plugin_config()` 解析此文件返回 `PluginManifest` 实例。

## 5. 解析器插件

### 创建步骤

1. 在 `parsers/` 下新建 `.py` 文件
2. 继承 `PluginBase`，实现 `parse(raw: str) -> ParseResult`
3. 可选：在 `templates/plugin.toml` 中声明元数据

### 最小示例

```python
# parsers/show_uptime.py
from engine.plugin_base import PluginBase, PluginManifest
from engine.parser_base import ParseResult

class ShowUptime(PluginBase):
    manifest = PluginManifest(
        name="show_uptime", version="1.0.0", author="me",
        description="解析系统运行时间", plugin_type="parser",
    )
    command = "show uptime"

    def parse(self, raw: str) -> ParseResult:
        return ParseResult(rows=[{"uptime": raw.strip()}])

    def validate(self) -> list[str]:
        return [] if self.command else ["command is empty"]
```

### 注册方式

- **自动发现**: 文件放入 `parsers/`，`PluginAwareParserRegistry` 自动扫描
- **entry_points**: 在 `pyproject.toml` 中声明（见第 11 节）

## 6. 告警规则插件

### 创建步骤

1. 在 `rules/` 下新建 `.py` 文件
2. 继承 `AlertRule`，定义 `name` / `description` 类变量
3. 实现 `evaluate(device_data: dict) -> list[AlertResult]`
4. 在 `rules/rules.yaml` 中配置阈值

### 最小示例

```python
# rules/cpu_high.py
from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity

class CpuHighRule(AlertRule):
    name = "cpu_high"
    description = "CPU 使用率过高告警"

    def evaluate(self, device_data: dict) -> list[AlertResult]:
        cpu = device_data.get("device_info", {}).get("cpu_usage", 0)
        threshold = self.config.get("max_cpu", 90)
        if cpu > threshold:
            return [AlertResult(
                rule_name=self.name, severity=AlertSeverity.WARNING,
                message=f"CPU {cpu}% 超过阈值 {threshold}%",
                device_ip=device_data.get("device_ip"),
            )]
        return []
```

### YAML 配置

```yaml
# rules/rules.yaml
rules:
  cpu_high:
    enabled: true
    max_cpu: 90
```

`AlertPluginManager.load_config()` 加载 YAML，`configure_rule()` 将 `enabled` 之外的字段注入 `rule.config`。

## 7. PluginManager API

```python
class PluginManager:
    def register(self, plugin: PluginBase) -> None
        # 调用 validate()，失败抛 PluginValidationError

    def discover(self, directory: str) -> list[str]
        # 扫描目录，导入模块，实例化 PluginBase 子类并注册

    def get_plugins(self, plugin_type: str) -> list[PluginBase]
    def get_plugin(self, name: str) -> PluginBase | None

    def execute(self, plugin_type: str, method: str, *args, **kwargs) -> list[Any]
        # 遍历指定类型插件调用 method，异常被捕获并记录，不影响其他插件

    def load_all(self, plugin_dirs: list[str]) -> dict[str, int]
        # 批量加载，返回 {plugin_type: count}

    def unload_all(self)
        # 调用所有插件的 on_unload()，清空注册表

    def topological_order(self, plugins: list[PluginBase]) -> list[PluginBase]
        # 按依赖关系拓扑排序（Kahn 算法）
```

## 8. AlertPluginManager API

```python
class AlertPluginManager:
    def discover_rules(self) -> int
        # 扫描 rules/ 目录，发现 AlertRule 子类

    def load_config(self, path: str) -> dict
        # 加载 YAML，返回 rules 键下的配置字典

    def configure_rule(self, rule: AlertRule, config: dict) -> AlertRule
        # 应用 enabled 标志和阈值配置

    def evaluate_all(self, device_data: dict) -> dict
        # 执行所有启用规则，返回 {"alerts": [...], "stats": {...}, "errors": [...]}

    def get_alerts(self, device_data: dict) -> list[AlertResult]
        # 便捷方法，仅返回告警列表
```

## 9. 配置

告警规则配置使用 YAML 格式，结构为 `rules.{rule_name}.{key}`。示例见 `rules/rules.example.yaml`，包含 `optics_power`、`interface_errors`、`storm_control`、`system_health` 四条规则。

## 10. 热重载

`engine/hot_reload.py` 基于 `watchdog` 实现开发期热重载：

```python
from engine.hot_reload import auto_start, auto_stop

auto_start("rules")   # 监控 rules/ 目录的 .py 变更
auto_stop()           # 停止监控
```

文件变更时自动清空并重新发现所有规则，新规则自动生效。

## 11. 分发

通过 `pyproject.toml` 的 `entry_points` 注册插件，支持 pip 安装：

```toml
[project.entry-points."switch_inspector.parsers"]
show_clock = "parsers.builtin_single:ShowClock"
show_version = "parsers.show_version:ShowVersion"

[project.entry-points."switch_inspector.rules"]
optics_power = "rules.optics_power:OpticsPowerRule"
interface_errors = "rules.interface_errors:InterfaceErrorsRule"
```

## 12. 容错

| 阶段 | 机制 | 效果 |
|------|------|------|
| 加载 | `validate()` 返回错误 → `PluginValidationError` | 跳过注册，记录结构化错误 |
| 运行时 | `execute()` 内 `try/except` | 单插件崩溃不影响其他 |
| 告警 | `evaluate_all()` 内 `try/except` | 单规则失败不影响其他 |
| 错误等级 | `_structured_error(severity="critical"\|"warning"\|"info")` | 按严重程度分类 |

## 13. 向后兼容

- `_wrap_plugin()`: 将 `PluginBase` 实例包装为 `BaseParser` 适配器，兼容旧版 `ParserRegistry`
- `_auto_manifest()`: 为旧式 `BaseParser` 自动生成 `PluginManifest`
- `deprecated_api(since, remove_in)`: 标记废弃 API，调用时触发 `DeprecationWarning`
- `PluginAwareParserRegistry`: 同时支持 `PluginBase` 和 `BaseParser` 两种风格

## 14. 最佳实践

- **命名**: 解析器用 `ShowXxx`，告警规则用 `XxxRule`
- **测试**: 使用 pytest，直接实例化插件并调用方法

```python
# tests/test_cpu_rule.py
from rules.cpu_high import CpuHighRule

def test_cpu_high_triggers_warning():
    rule = CpuHighRule()
    rule.config = {"max_cpu": 50}
    result = rule.evaluate({"device_info": {"cpu_usage": 80}})
    assert len(result) == 1
    assert result[0].severity.name == "WARNING"
```

- **配置**: 所有阈值在 YAML 中声明，不要在代码中硬编码
- **依赖**: 通过 `manifest.dependencies` 声明，`topological_order()` 保证加载顺序
- **异常**: 不要在 `evaluate()` 中抛异常，返回空列表表示无告警
