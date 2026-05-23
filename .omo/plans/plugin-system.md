# 插件系统完善方案

## TL;DR

> **Quick Summary**: 修补现有 parsers 插件短板（增加 manifest/validate/version/protocol），以告警规则为试点实现新的可插拔模块类型，输出完整的插件接口规范文档。
> 
> **Deliverables**:
> - 插件基础协议与 PluginManager
> - 告警规则插件系统（4 个具体规则：光功率、错误计数、风暴控制、系统健康）
> - Parsers 插件迁移（向后兼容）
> - 插件接口规范文档
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: 测试框架 → PluginManager → 告警 Hook 接口 → 规则实现 → report.py 集成

---

## Context

### Original Request
> "拟定方案完善、丰富插件功能，需要详细说明接口与插件规范，评估将目前的功能插件化的必要性"

### Interview Summary
**Key Discussions**:
- **目标用户**: 混合 — 网工用声明式 YAML 配阈值，开发者用 Python API 写复杂告警逻辑
- **插件化范围**: 本次聚焦告警规则 + parsers 补齐；合规检查、字段处理器、文件适配器为后续迭代
- **分发方式**: 项目内目录 (`plugins/`) + pip `entry_points` 双通道
- **容错策略**: 分层 — 加载时 schema 校验 + 运行时 try/catch 隔离，一个插件崩不影响其他
- **配置管理**: 插件自声明 schema（plugin.toml），用户在主配置 YAML 提供值
- **动态加载**: 开发模式 watchdog 热重载，生产模式重启生效
- **兼容策略**: 渐进迁移 — 旧 `BaseParser.parse()` 继续工作 30 天，标 deprecated
- **测试策略**: TDD 新接口，项目零测试 → 从零搭建
- **MVP**: 告警规则插件化 + 完整规范

**Research Findings**:
- **pluggy** (pytest 内核): `@hookspec`/`@hookimpl` 装饰器模式，LIFO 执行，`PluginManager` 管理所有
- **entry_points** (Python 标准): `pyproject.toml` → `importlib.metadata.entry_points()`，pip 包零配置发现
- **`__init_subclass__`**: 同项目内继承即注册，零样板代码
- **stevedore**: OpenStack 生产级插件库，Driver(单)/Extension(多)/Named(指定) 三模式

**代码勘探关键发现**:
- `BaseParser` 接口不错但缺 `validate()` / `version` / `metadata`
- `ParserRegistry` 手工注册 + 手工加载，无统一发现协议
- `build_report()` 中所有阈值硬编码：`-15dBm`、`-20dBm`、`>100 errors`
- 项目**零测试文件** — 需从零搭建测试框架
- 全局状态集中在 FastAPI `lifespan`，适合注入 PluginManager

### 自评估 Gap 分析
- ⚠ **测试框架选择**: 项目无测试，需决定 pytest vs bun test。pytest 更生态成熟，bun test 更简洁
- ⚠ **向后兼容边界**: 旧 `parse()` 签名保留多久？建议 3 个小版本后移除
- ⚠ **热重载安全性**: watchdog 在生产禁用以防竞态，但需文档说明
- ✓ **Scope 锁定**: 合规检查/字段处理器/文件适配器明确为后续迭代，本次不碰

---

## Work Objectives

### Core Objective
补齐现有 parsers 插件缺失的元数据/验证/版本能力，以告警规则为试点建立统一的插件协议与生命周期管理，输出可复制的接口规范。

### Concrete Deliverables
- `engine/plugin_base.py` — 通用插件协议 (PluginManifest, PluginBase ABC)
- `engine/plugin_manager.py` — 统一加载/注册/生命周期管理
- `engine/alert_rules.py` — 告警规则 Hook 接口
- `plugins/alerts/optical_power.py` — 光功率告警规则
- `plugins/alerts/error_counters.py` — 错误计数告警规则
- `plugins/alerts/storm_control.py` — 风暴控制合规规则
- `plugins/alerts/system_health.py` — 系统健康告警规则
- `engine/report.py` — 重构为消费告警插件
- `tests/` — TDD 测试框架 + 告警规则测试
- `docs/plugin-spec.md` — 插件接口规范文档

### Definition of Done
- [ ] `bun test` 全部通过（至少 15 个测试用例）
- [ ] 4 个告警规则插件独立可运行，不需要修改核心代码即可添加新规则
- [ ] 现有 11 个 parsers 插件零改动（或仅加 manifest 文件）
- [ ] scan → preview → report 全链路通过，告警结果与重构前一致
- [ ] 规范文档包含：接口定义、生命周期、配置 schema、示例代码

### Must Have
- 统一的插件发现与注册协议
- 插件元数据（名称、版本、作者、描述）
- 插件自验证（加载前校验必要条件）
- 运行时错误隔离（一个插件崩不影响其他）
- 告警规则可插拔（新增告警只需加文件，不改 report.py）
- 向后兼容（现有 parsers 零破坏）
- 插件接口规范文档

### Must NOT Have (Guardrails)
- ❌ 不创建 npm/webpack 构建步骤
- ❌ 不引入重量级依赖（除 watchdog 可选项外）
- ❌ 不修改 splitter.py / normalizer.py / exporter.py
- ❌ 不创建数据库或持久化层
- ❌ 不实现合规检查/字段处理器/文件适配器的插件化（本次）
- ❌ 不实现 web UI 管理插件（不需要 CRUD 界面）
- ❌ 不实现插件市场/远程下载

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO（零测试文件）
- **Automated tests**: TDD — 先写测试，再实现
- **Framework**: `bun test`（与项目 JS runtime 一致，零配置，内置 assert）
- **Test location**: `tests/` 目录，镜像 `engine/` 结构

### QA Policy
每个任务包含 agent-executed QA 场景。
- **Backend/Python**: 使用 Bash 运行 `bun test` 验证
- **API**: curl 请求 `/api/report` 验证告警结果
- **CLI**: 直接 `python3 -c "import ..."` 验证导入和注册

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — 测试 + 协议):
├── Task 1: 测试框架搭建 [quick]
├── Task 2: PluginManifest + PluginBase ABC [quick]
├── Task 3: PluginManager 核心 [quick]
└── Task 4: plugin.toml schema [quick]

Wave 2 (Parsers 迁移 — 向后兼容):
├── Task 5: ParserRegistry → PluginManager 协议适配 [deep]
├── Task 6: 现有 parsers 添加 manifest [quick]
├── Task 7: BaseParser 增强 (validate + deprecated 路径) [quick]
└── Task 8: 插件加载错误分级与 UI 反馈 [visual-engineering]

Wave 3 (告警规则插件 — MVP):
├── Task 9: AlertRule Hook 接口设计 [deep]
├── Task 10: 光功率告警规则 (port from report.py) [deep]
├── Task 11: 错误计数告警规则 [deep]
├── Task 12: 风暴控制合规规则 [deep]
├── Task 13: 系统健康告警规则 [deep]
├── Task 14: AlertPluginManager + 规则执行引擎 [deep]
└── Task 15: 告警 YAML 模板 (低代码方式配阈值) [quick]

Wave 4 (集成 + 规范):
├── Task 16: 重构 build_report() 消费告警插件 [deep]
├── Task 17: Watchdog 热重载 (dev mode) [quick]
├── Task 18: entry_points 发现支持 [quick]
└── Task 19: 插件接口规范文档 [writing]

Wave FINAL:
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real manual QA [unspecified-high]
├── Task F4: Scope fidelity check [deep]
└── → User okay
```

Critical Path: Task 1 → Task 3 → Task 9 → Task 14 → Task 16 → F1-F4

### Agent Dispatch Summary
- **Wave 1**: 4 tasks, all quick/deep
- **Wave 2**: 4 tasks, mixed
- **Wave 3**: 7 tasks, deep/quick
- **Wave 4**: 4 tasks, deep/quick/writing
- **Wave FINAL**: 4 review tasks

### Dependency Matrix
- **1**: — → 2, 3, 4, 5
- **2**: — → 3, 6
- **3**: 2 → 5, 9, 14
- **4**: — → 6, 19
- **5**: 1, 3 → 6, 7, 8
- **6**: 2, 4, 5 → —
- **7**: 5 → 8
- **8**: 5, 7 → —
- **9**: 3, 5 → 10, 11, 12, 13, 14, 15
- **10**: 9 → 14, 16
- **11**: 9 → 14, 16
- **12**: 9 → 14, 16
- **13**: 9 → 14, 16
- **14**: 3, 9, 10, 11, 12, 13 → 16
- **15**: 9 → 16
- **16**: 10, 11, 12, 13, 14, 15 → F1-F4
- **17**: 3 → —
- **18**: 3 → —
- **19**: 4, 9, 14 → —

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **FORMAT**: Task labels MUST use bare numbers: `1.`, `2.`, `3.` — NOT `T1.`, `Task 1.`, `Phase 1:`.
> Final Verification Wave labels MUST use `F1.`, `F2.`, etc.

- [ ] 1. 测试框架搭建

  **What to do**:
  - 在项目根目录创建 `tests/` 目录
  - 选择 `bun test` 作为测试框架（使用项目内 Python 测试能力: 通过 `python3 -m pytest` 或直接用 `python3 -c` + assert）
  - 创建 `tests/conftest.py` — 共享 fixtures（mock registry, 样本 parsed_data, 样本日志输出）
  - 创建 `tests/test_plugin_base.py` — 占位测试（1 个恒真测试验证框架可用）
  - 创建 `tests/test_parser_base.py` — BaseParser 基础测试（构造一个简单 parser, 调用 parse(), 验证返回 ParseResult）
  - 在 `package.json` 或 Makefile 添加 `test` 命令
  - 运行 `python3 -m pytest tests/ -v` → 全部绿

  **Must NOT do**:
  - 不安装 JS 测试框架（不做 npm install）
  - 不创建复杂的 mock 体系（仅 conftest.py fixtures）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯基础设施搭建，无业务逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5, 6, 7, 8
  - **Blocked By**: None (can start immediately)

  **References**:
  - `engine/parser_base.py:24-30` — BaseParser 接口定义（构造测试用例时需要）
  - `engine/parser_base.py:8-15` — FieldDef dataclass（创建测试数据时参考）
  - `engine/parser_base.py:18-21` — ParseResult dataclass（验证 parse() 返回值）

  **Acceptance Criteria**:
  - [ ] `tests/` 目录存在且包含 `conftest.py`、`__init__.py`、`test_plugin_base.py`、`test_parser_base.py`
  - [ ] `python3 -m pytest tests/ -v` → PASS（至少 2 个测试通过）
  - [ ] 测试命令可重复运行（无状态泄漏）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 测试框架可用 — 运行占位测试
    Tool: Bash
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -m pytest tests/test_plugin_base.py -v
    Expected Result: 输出显示 1 passed（占位测试通过）
    Failure Indicators: 任何 ImportError 或 ModuleNotFoundError
    Evidence: .omo/evidence/task-1-framework-setup.txt

  Scenario: BaseParser 基础功能测试通过
    Tool: Bash
    Steps:
      1. python3 -m pytest tests/test_parser_base.py -v
      2. 确认测试覆盖: BaseParser.parse() 返回类型、ParseResult.rows 非空
    Expected Result: 输出显示所有 test_parser_base 测试通过
    Failure Indicators: AssertionError 或测试不通过
    Evidence: .omo/evidence/task-1-parser-test.txt
  ```

  **Commit**: YES
  - Message: `test: add test framework + BaseParser tests`
  - Files: `tests/`, `package.json` (if modified)

---

- [ ] 2. PluginManifest + PluginBase ABC

  **What to do**:
  - 创建 `engine/plugin_base.py`（新文件，通用插件协议）
  - 定义 `PluginManifest` dataclass:
    - `name: str` — 插件唯一标识
    - `version: str` — semver 版本号
    - `author: str` — 作者
    - `description: str` — 功能描述
    - `plugin_type: str` — 插件类型 (parser/alert/compliance/processor/adapter)
    - `dependencies: List[str]` — 依赖的插件 name 列表
    - `config_schema: Dict` — JSON Schema 格式的配置声明
    - `entry_point: str` — 入口模块路径（如 `parsers.show_version`）
  - 定义 `PluginBase` ABC:
    - `manifest: ClassVar[PluginManifest]` — 类级属性（从 plugin.toml 或装饰器注入）
    - `validate() -> List[str]` — 自校验，返回错误列表（空=通过）
    - `on_load()` — 加载后初始化（可选，默认空实现）
    - `on_unload()` — 卸载前清理（可选，默认空实现）
  - 创建 `engine/plugin_exceptions.py`:
    - `PluginValidationError` — 校验失败
    - `PluginLoadError` — 加载失败
    - `PluginRuntimeError` — 运行时错误（隔离用）
  - 写入 `tests/test_plugin_base.py` — 完整测试：
    - 测试 PluginManifest 字段完整性
    - 测试 validate() 返回空列表（合法插件）
    - 测试 validate() 返回错误列表（不合法插件）
    - 测试 PluginBase 不能直接实例化（ABC 约束）

  **Must NOT do**:
  - 不修改 `engine/parser_base.py`（旧的 BaseParser 保持不动）
  - 不在 PluginBase 中耦合解析器逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯 dataclass + ABC 定义，无复杂逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 3, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `engine/parser_base.py:24-30` — 现有 BaseParser 设计（保持风格一致）
  - `engine/parser_base.py:8-15` — FieldDef dataclass 模式（参考其 dataclass 风格）
  - 官方文档: `https://docs.python.org/3/library/abc.html` — ABC 正确用法
  - 官方文档: `https://docs.python.org/3/library/dataclasses.html` — dataclass field 选项
  - 官方文档: `https://docs.python.org/3/library/typing.html#typing.ClassVar` — ClassVar 用法

  **Acceptance Criteria**:
  - [ ] `engine/plugin_base.py` 包含 PluginManifest + PluginBase ABC
  - [ ] `engine/plugin_exceptions.py` 包含 3 个异常类
  - [ ] `python3 -m pytest tests/test_plugin_base.py -v` → 所有测试通过（≥ 4 个测试用例）
  - [ ] `from engine.plugin_base import PluginBase, PluginManifest` 导入成功

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 合法插件 — validate() 通过
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_base import PluginBase, PluginManifest
  class GoodPlugin(PluginBase):
      manifest = PluginManifest(name='test', version='1.0.0', author='qa', description='test', plugin_type='alert', dependencies=[], config_schema={}, entry_point='test')
      def validate(self): return []
  p = GoodPlugin()
  errors = p.validate()
  assert errors == [], f'Expected empty list, got {errors}'
  print('PASS: validate() returned []')
  "
    Expected Result: 输出 "PASS: validate() returned []"
    Failure Indicators: AssertionError 或 ABC TypeError
    Evidence: .omo/evidence/task-2-validate-pass.txt

  Scenario: 不合法插件 — validate() 返回错误
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_base import PluginBase, PluginManifest
  class BadPlugin(PluginBase):
      manifest = PluginManifest(name='bad', version='1.0.0', author='qa', description='bad plugin', plugin_type='alert', dependencies=[], config_schema={}, entry_point='bad')
      def validate(self): return ['missing required config']
  assert len(BadPlugin().validate()) == 1
  print('PASS: validate() correctly returned errors')
  "
    Expected Result: "PASS: validate() correctly returned errors"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-2-validate-fail.txt
  ```

  **Commit**: YES
  - Message: `feat(plugin): add PluginManifest + PluginBase ABC + exceptions`
  - Files: `engine/plugin_base.py`, `engine/plugin_exceptions.py`, `tests/test_plugin_base.py`

---

- [ ] 3. PluginManager 核心

  **What to do**:
  - 创建 `engine/plugin_manager.py`（核心编排器）
  - 实现 `PluginManager` 类：
    - `__init__()` — 初始化空注册表 `_registry: Dict[str, Dict[str, PluginBase]]`（按 plugin_type 分组）
    - `register(plugin: PluginBase) -> None` — 注册插件（先调 validate()，失败抛 PluginValidationError 并记录）
    - `discover(directory: str) -> List[str]` — 扫描目录，`importlib` 加载模块，`inspect` 找 PluginBase 子类
    - `get_plugins(plugin_type: str) -> List[PluginBase]` — 按类型获取
    - `get_plugin(name: str) -> Optional[PluginBase]` — 按名称获取
    - `execute(plugin_type: str, method: str, *args, **kwargs) -> List[Any]` — 按类型批量执行方法，隔离异常
    - `topological_order(plugins: List[PluginBase]) -> List[PluginBase]` — 依赖拓扑排序（Kahn 算法）
    - `load_all(plugin_dirs: List[str]) -> Dict[str, int]` — 批量加载，返回 {type: count}
    - `unload_all()` — 按加载逆序卸载（调 on_unload）
  - 实现全局单例 `get_plugin_manager()` → `PluginManager`
  - 写入 `tests/test_plugin_manager.py`：
    - 注册/获取/按类型获取
    - validate() 失败时拒绝注册
    - execute() 隔离异常（一个插件崩，其他仍执行）
    - 拓扑排序（有依赖和无依赖场景）
    - load_all 后插件数量正确

  **Must NOT do**:
  - 不在此任务实现 entry_points 发现（Task 18）
  - 不在 PluginManager 中耦合 FastAPI 生命周期

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 核心数据结构 + 简单算法（拓扑排序），无外部依赖

  **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5, 9, 14, 17, 18
  - **Blocked By**: Task 2 (需要 PluginBase)

  **References**:
  - `engine/plugin_base.py` — PluginBase/PluginManifest/异常类（Task 2 产物）
  - `engine/registry.py:76-110` — 现有 load_custom_parsers() 的发现模式（pkgutil + importlib + inspect）
  - 算法参考: Kahn's algorithm for topological sort — `https://en.wikipedia.org/wiki/Topological_sorting`

  **Acceptance Criteria**:
  - [ ] `engine/plugin_manager.py` 包含 PluginManager 类 + get_plugin_manager()
  - [ ] `python3 -m pytest tests/test_plugin_manager.py -v` → 所有测试通过（≥ 6 个测试用例）
  - [ ] 拓扑排序正确处理: 无依赖 2 插件 → 顺序无关；A 依赖 B → B 在 A 前
  - [ ] execute() 异常隔离: 3 个插件中 1 个崩 → 另外 2 个正常执行并返回结果

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 注册 + 获取 + 类型过滤
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_base import PluginBase, PluginManifest
  from engine.plugin_manager import PluginManager

  class AlertA(PluginBase):
      manifest = PluginManifest(name='alert_a', version='1.0', author='qa', description='a', plugin_type='alert', dependencies=[], config_schema={}, entry_point='a')
      def validate(self): return []

  class AlertB(PluginBase):
      manifest = PluginManifest(name='alert_b', version='1.0', author='qa', description='b', plugin_type='alert', dependencies=['alert_a'], config_schema={}, entry_point='b')
      def validate(self): return []

  pm = PluginManager()
  pm.register(AlertA())
  pm.register(AlertB())
  assert len(pm.get_plugins('alert')) == 2
  assert pm.get_plugin('alert_a') is not None
  ordered = pm.topological_order(pm.get_plugins('alert'))
  assert ordered[0].manifest.name == 'alert_a'  # A before B
  print('PASS')
  "
    Expected Result: "PASS"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-3-register-topo.txt

  Scenario: execute() 异常隔离
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_base import PluginBase, PluginManifest
  from engine.plugin_manager import PluginManager

  class Good(PluginBase):
      manifest = PluginManifest(name='g', version='1', author='qa', description='g', plugin_type='test', dependencies=[], config_schema={}, entry_point='g')
      def validate(self): return []
      def run(self): return 'ok'

  class Bad(PluginBase):
      manifest = PluginManifest(name='b', version='1', author='qa', description='b', plugin_type='test', dependencies=[], config_schema={}, entry_point='b')
      def validate(self): return []
      def run(self): raise RuntimeError('boom')

  pm = PluginManager()
  pm.register(Good())
  pm.register(Bad())
  results = pm.execute('test', 'run')
  assert 'ok' in results
  assert len(results) == 2  # Bad 插件也返回了（None 或异常占位）
  print('PASS: exception isolated')
  "
    Expected Result: "PASS: exception isolated"
    Failure Indicators: 未捕获的 RuntimeError 导致脚本崩溃
    Evidence: .omo/evidence/task-3-isolation.txt
  ```

  **Commit**: YES
  - Message: `feat(plugin): add PluginManager core with registration, discovery, topological sort, error isolation`
  - Files: `engine/plugin_manager.py`, `tests/test_plugin_manager.py`

---

- [ ] 4. plugin.toml schema 定义

  **What to do**:
  - 创建 `engine/plugin_config.py`
  - 定义 `load_plugin_config(path: str) -> PluginManifest` 函数 — 从 TOML 文件加载 manifest
  - 支持字段:
    ```toml
    [plugin]
    name = "optical_power_alert"
    version = "1.0.0"
    author = "netops team"
    description = "光模块接收功率异常检测"
    type = "alert"
    entry_point = "plugins.alerts.optical_power:OpticalPowerAlert"

    [plugin.dependencies]
    # alert 插件通常无依赖

    [plugin.config]
    # JSON Schema 格式
    rx_power_warn_threshold = {type = "number", default = -15.0, description = "RX power warning threshold (dBm)"}
    rx_power_crit_threshold = {type = "number", default = -20.0, description = "RX power critical threshold (dBm)"}
    ```
  - Python 侧创建 `PluginConfig` dataclass 方便代码访问
  - 写入 `tests/test_plugin_config.py` — 用临时文件测试 TOML 解析
  - 依赖：`pip install toml` (或 Python 3.11+ 使用 `tomllib`)
  - 写入 `templates/plugin.example.toml` — 完整注释示例

  **Must NOT do**:
  - 不在此任务实现 watch 这个 TOML 文件的热重载
  - 不实现 web UI 编辑插件配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: TOML 解析 + dataclass 映射，简单直接
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 6, 19
  - **Blocked By**: None (can start immediately)

  **References**:
  - `engine/plugin_base.py` — PluginManifest dataclass 字段定义（Task 2 产物）
  - `templates/textfsm_mapping.yaml` — 现有 YAML 配置文件风格（参考项目配置风格）
  - 官方文档: `https://docs.python.org/3/library/tomllib.html` — Python 3.11+ tomllib API

  **Acceptance Criteria**:
  - [ ] `engine/plugin_config.py` 包含 `load_plugin_config()` 和 `PluginConfig`
  - [ ] `templates/plugin.example.toml` 完整示例文件存在
  - [ ] `python3 -m pytest tests/test_plugin_config.py -v` → PASS（≥ 2 个测试用例）
  - [ ] TOML 解析错误时有清晰的错误提示

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 合法 TOML → PluginManifest
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_config import load_plugin_config
  # 使用 templates/plugin.example.toml
  manifest = load_plugin_config('templates/plugin.example.toml')
  assert manifest.name == 'optical_power_alert'
  assert manifest.plugin_type == 'alert'
  print('PASS: TOML loaded correctly')
  "
    Expected Result: "PASS: TOML loaded correctly"
    Failure Indicators: FileNotFoundError 或 AssertionError
    Evidence: .omo/evidence/task-4-toml-load.txt

  Scenario: 非法 TOML → 友好错误
    Tool: Bash
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  import tempfile, os
  with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
      f.write('[plugin]\nname = \n')  # 语法错误
      tmp = f.name
  try:
      from engine.plugin_config import load_plugin_config
      load_plugin_config(tmp)
      print('FAIL: should have raised')
  except Exception as e:
      print(f'EXPECTED ERROR: {e}')
  finally:
      os.unlink(tmp)
  "
    Expected Result: 输出 "EXPECTED ERROR: ..." 包含有意义的错误描述
    Failure Indicators: 未捕获异常或错误描述模糊
    Evidence: .omo/evidence/task-4-toml-error.txt
  ```

  **Commit**: YES
  - Message: `feat(plugin): add plugin.toml schema + load_plugin_config()`
  - Files: `engine/plugin_config.py`, `templates/plugin.example.toml`, `tests/test_plugin_config.py`

---

- [ ] 5. ParserRegistry → PluginManager 协议适配

  **What to do**:
  - 在 `engine/registry.py` 中新增 `PluginAwareParserRegistry(ParserRegistry)` 子类
  - 改写 `load_custom_parsers()` — 不再直接 `inspect.getmembers` + `register_custom`，改为：
    1. 用 `PluginManager.discover(parsers_paths)` 发现所有 PluginBase 子类
    2. 调用 `plugin.validate()` 预检
    3. 检验失败的不注册，记录到 `_load_errors`
    4. 检验通过的包装为兼容层，注册到 `self._custom_parsers`
  - 新增 `_wrap_plugin(plugin: PluginBase) -> BaseParser` 适配器（将新接口映射到旧 `parse()` / `command` / `fields`）
  - 保持 `ParserRegistry.parse()` / `resolve()` 的对外签名不变
  - `load_textfsm_parsers()` 不做改动（TextFSM 仍走 YAML）
  - 写入 `tests/test_registry_plugin.py` — 测试：
    - 新风格 parser（带 manifest + validate）能被正确发现和注册
    - 旧风格 parser（无 manifest）仍然工作（兼容模式，默认 manifest）
    - validate 失败的 parser 不被注册
    - `get_load_errors()` 包含校验失败信息

  **Must NOT do**:
  - 不删除 `BaseParser` / `FixedWidthTableParser` / `KVPParser` / `BlockParser`
  - 不在本次标记 BaseParser 为 deprecated（Task 7 做）
  - 不改动现有 11 个 parsers 的源码

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 涉及兼容层设计、发现协议变更、多路径覆盖测试，需谨慎处理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 Wave 1 所有产物）
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 6, 7, 8
  - **Blocked By**: Task 1, 3

  **References**:
  - `engine/registry.py:76-110` — 现有 load_custom_parsers()（要改写的目标）
  - `engine/registry.py:29-84` — ParserRegistry 完整类（了解继承结构）
  - `engine/plugin_base.py` — PluginBase/PluginManifest（Task 2 产物）
  - `engine/plugin_manager.py` — PluginManager.discover()（Task 3 产物，理解发现 API）
  - `parsers/show_interfaces_transceiver.py` — 一个典型 parser 示例（测试兼容性时参考）
  - `templates/textfsm_mapping.yaml` — TextFSM 映射（不在本次改写范围，只参考）

  **Acceptance Criteria**:
  - [ ] `engine/registry.py` 新增 `PluginAwareParserRegistry` 类
  - [ ] 旧风格 parser（无 manifest）自动生成默认 PluginManifest
  - [ ] 新风格 parser（带 manifest + validate）的 validate 结果影响注册
  - [ ] `python3 -m pytest tests/test_registry_plugin.py -v` → PASS（≥ 4 个测试用例）
  - [ ] 现有 11 个 parsers 无需修改源码仍能加载

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 旧 parser 兼容 — 自动生成 manifest
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.registry import PluginAwareParserRegistry
  from engine.plugin_base import PluginBase
  reg = PluginAwareParserRegistry()
  reg.load_custom_parsers()
  # show_version parser 应被成功加载
  assert reg.has('show version'), 'show version parser not found'
  # 验证自动生成的 manifest
  p = reg._custom_parsers['show version']
  print(f'PASS: {len(reg._custom_parsers)} parsers loaded, show_version found')
  "
    Expected Result: 输出 "PASS: N parsers loaded, show_version found" (N ≥ 11)
    Failure Indicators: KeyError, ImportError
    Evidence: .omo/evidence/task-5-legacy-compat.txt

  Scenario: validate 失败的 parser 不被注册
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  import tempfile, os, sys
  # 创建临时非法 parser
  d = tempfile.mkdtemp()
  with open(os.path.join(d, 'bad_parser.py'), 'w') as f:
      f.write('''
  from engine.plugin_base import PluginBase, PluginManifest
  class BadParser(PluginBase):
      manifest = PluginManifest(name='bad', version='1', author='x', description='x', plugin_type='parser', dependencies=[], config_schema={}, entry_point='bad')
      command = 'bad cmd'
      fields = []
      def validate(self): return ['missing required fields']
      def parse(self, raw): return None
  ''')
  sys.path.insert(0, d)
  from engine.registry import PluginAwareParserRegistry
  reg = PluginAwareParserRegistry()
  # 不应因验证失败而崩溃
  errors = reg.get_load_errors()
  assert any('bad' in e.lower() for e in errors), f'Expected validation error in: {errors}'
  print('PASS: bad parser rejected')
  "
    Expected Result: "PASS: bad parser rejected"
    Failure Indicators: 未捕获异常导致脚本退出
    Evidence: .omo/evidence/task-5-validation-reject.txt
  ```

  **Commit**: YES
  - Message: `refactor(registry): add PluginAwareParserRegistry with plugin protocol support`
  - Files: `engine/registry.py`, `tests/test_registry_plugin.py`

---

- [ ] 6. 现有 parsers 添加 manifest

  **What to do**:
  - 为 project 内 11 个 parsers 的 **每个** 创建对应的 `plugin.toml` 文件
  - TOML 文件放在 parser 同目录下，命名规则：`{module_name}.plugin.toml`
  - 例如 `parsers/show_version.plugin.toml`:
    ```toml
    [plugin]
    name = "show_version"
    version = "1.0.0"
    author = "netops"
    description = "解析 show version 输出，提取设备型号/软件版本/序列号"
    type = "parser"
    entry_point = "parsers.show_version:ShowVersionParser"
    
    [plugin.config]
    # parser 通常无额外配置
    ```
  - 确保所有 11 个 TOML 文件都正确引用 `entry_point`
  - **不修改任何 parser 的 Python 源码**（仅添加 TOML 文件）
  - 运行 `python3 -m pytest tests/test_registry_plugin.py` 验证全部通过

  **Must NOT do**:
  - 不修改 parsers/*.py 内的任何代码
  - 不在 TOML 里定义复杂的 config（parsers 不需要）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯文案/配置添加，重复×11，无逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8)
  - **Blocks**: None
  - **Blocked By**: Task 2 (PluginManifest), Task 4 (plugin.toml schema), Task 5 (PluginAwareParserRegistry)

  **References**:
  - `templates/plugin.example.toml` — TOML 模板/示例（Task 4 产物，直接照抄格式）
  - `parsers/` 目录 — 11 个 parser 文件列表（确认所有文件名）
  - `parsers/show_interfaces_transceiver.py` — 典型 parser（确认 class name 和 command）

  **Acceptance Criteria**:
  - [ ] 11 个 `*.plugin.toml` 文件全部创建且格式正确
  - [ ] `python3 -m pytest tests/test_registry_plugin.py -v` → PASS
  - [ ] 每个 TOML 的 `entry_point` 指向正确的 Module:Class

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 所有 11 个 parsers 通过 plugin 方式加载
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.registry import PluginAwareParserRegistry
  reg = PluginAwareParserRegistry()
  reg.load_custom_parsers()
  count = len(reg._custom_parsers)
  assert count >= 11, f'Expected >= 11 parsers, got {count}'
  print(f'PASS: {count} parsers loaded via plugin protocol')
  "
    Expected Result: "PASS: N parsers loaded via plugin protocol" (N ≥ 11)
    Failure Indicators: 少于 11，或 ImportError
    Evidence: .omo/evidence/task-6-all-parsers.txt
  ```

  **Commit**: YES
  - Message: `feat(parsers): add plugin.toml manifests for all 11 parsers`
  - Files: `parsers/*.plugin.toml` (11 files)

---

- [ ] 7. BaseParser 增强 (validate + deprecated 路径)

  **What to do**:
  - 在 `engine/parser_base.py` 的 `BaseParser` 类中新增：
    - `version: ClassVar[str] = "1.0.0"` — 解析器版本
    - `validate() -> List[str]` 方法（默认返回 `[]`，子类可覆盖）
    - 装饰器 `@deprecated_api(since: str, remove_in: str)` — 标记旧 API
    - `__init_subclass__` 钩子 — 子类创建时自动注册到 PluginManager（如果 PluginManager 已初始化）
  - 更新 `FixedWidthTableParser` / `KVPParser` / `BlockParser` 不强制覆盖
  - 写入 `tests/test_parser_base_enhanced.py` — 测试：
    - BaseParser.validate() 默认返回 []
    - 子类可覆盖 validate() 返回错误
    - version 默认值和覆盖值
    - deprecated_api 装饰器发出 DeprecationWarning
    - __init_subclass__ 自动注册

  **Must NOT do**:
  - 不修改 `parse()` 签名（破坏兼容）
  - 不强制现有 parsers 实现 validate()（默认空列表）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 给现有类加属性/方法/装饰器，少量增量代码
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 8)
  - **Blocks**: Task 8
  - **Blocked By**: Task 5

  **References**:
  - `engine/parser_base.py:24-30` — BaseParser 当前定义（修改目标）
  - `engine/plugin_base.py` — PluginBase.validate() 接口（保持签名一致）
  - `engine/plugin_manager.py` — get_plugin_manager()（自动注册时调用）

  **Acceptance Criteria**:
  - [ ] BaseParser 新增 `version`、`validate()`、`__init_subclass__`
  - [ ] `python3 -m pytest tests/test_parser_base_enhanced.py -v` → PASS（≥ 4 个测试用例）
  - [ ] 现有 11 个 parsers 的 parse() 行为完全不变

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 默认 validate 返回空列表
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.parser_base import BaseParser
  class P(BaseParser):
      command = 'test'
      fields = []
      def parse(self, raw): return None
  p = P()
  assert p.validate() == []
  print('PASS: default validate() returns []')
  "
    Expected Result: "PASS: default validate() returns []"
    Failure Indicators: AssertionError 或 AttributeError
    Evidence: .omo/evidence/task-7-validate-default.txt

  Scenario: 子类覆盖 validate() 返回错误
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.parser_base import BaseParser
  class P(BaseParser):
      command = 'test'
      fields = []
      def parse(self, raw): return None
      def validate(self): return ['error: no fields defined']
  assert len(P().validate()) == 1
  print('PASS: custom validate() works')
  "
    Expected Result: "PASS: custom validate() works"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-7-validate-custom.txt
  ```

  **Commit**: YES
  - Message: `feat(parser): add validate(), version, __init_subclass__ to BaseParser`
  - Files: `engine/parser_base.py`, `tests/test_parser_base_enhanced.py`

---

- [ ] 8. 插件加载错误分级与 UI 反馈

  **What to do**:
  - 在 `engine/registry.py` 中增强 `_load_errors`：
    - 每个错误携带 `severity` 字段（"critical" / "warning" / "info"）
    - 错误结构化：`{"plugin": name, "severity": str, "message": str, "suggestion": str}`
  - 在 `main.py` 的 `/api/scan` 返回中，按 severity 分组展示：
    ```json
    "plugin_status": {
      "loaded": 14,
      "failed_critical": 0,
      "failed_warning": 1,
      "errors": [
        {"plugin": "show_xxx", "severity": "warning", "message": "config_schema incomplete", "suggestion": "Add [plugin.config] to plugin.toml"}
      ]
    }
    ```
  - 在 `ui/templates/index.html` 中添加插件状态区域（仅在 `failed > 0` 时显示），用颜色区分 severity：
    - critical: 红色，警告号 + 建议修复步骤
    - warning: 黄色，提示但不阻断
    - info: 灰色，纯信息
  - 写入 `tests/test_plugin_ui_feedback.py` — 测试错误分级逻辑

  **Must NOT do**:
  - 不添加 WebSocket 实时推送
  - 不大改 UI 布局（仅在现有卡片下方追加状态区）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 涉及 HTML 模板修改 + 前端颜色选择
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（Wave 2 中最后执行，依赖其他 Wave 2 任务）
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Task 5, 7

  **References**:
  - `main.py:114-126` — 现有 /api/scan 返回结构（扩展目标）
  - `main.py:68-72` — index.html 模板路径
  - `ui/templates/index.html` — 当前 UI 模板（追加状态区的位置）
  - `engine/registry.py:29-41` — ParserRegistry 构造函数 + _load_errors 当前定义

  **Acceptance Criteria**:
  - [ ] `_load_errors` 中每个错误带 `severity` + `suggestion`
  - [ ] `/api/scan` 返回新增 `plugin_status` 字段
  - [ ] UI 在加载失败时显示彩色状态卡片
  - [ ] `python3 -m pytest tests/test_plugin_ui_feedback.py -v` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 错误分级输出
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.registry import ParserRegistry
  reg = ParserRegistry()
  reg._load_errors = [
      {'plugin': 'bad_parser', 'severity': 'critical', 'message': 'syntax error', 'suggestion': 'fix syntax'},
      {'plugin': 'slow_parser', 'severity': 'warning', 'message': 'slow import', 'suggestion': 'optimize'},
  ]
  criticals = [e for e in reg._load_errors if e['severity'] == 'critical']
  warnings = [e for e in reg._load_errors if e['severity'] == 'warning']
  assert len(criticals) == 1
  assert len(warnings) == 1
  print('PASS: error severity classification works')
  "
    Expected Result: "PASS: error severity classification works"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-8-error-severity.txt

  Scenario: API 返回 plugin_status
    Tool: Bash (curl)
    Steps:
      1. 启动服务: python3 main.py（或使用测试模式检查返回结构）
      2. python3 -c "
  # 构造模拟 scan 响应检查 plugin_status 字段
  import json
  mock_resp = {'file_count': 5, 'plugin_status': {'loaded': 14, 'failed_warning': 1}}
  assert 'plugin_status' in mock_resp
  assert mock_resp['plugin_status']['loaded'] == 14
  print('PASS: plugin_status field present')
  "
    Expected Result: "PASS: plugin_status field present"
    Failure Indicators: KeyError
    Evidence: .omo/evidence/task-8-api-status.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): add plugin load status with severity levels to scan response`
  - Files: `engine/registry.py`, `main.py`, `ui/templates/index.html`, `tests/test_plugin_ui_feedback.py`

---

- [ ] 9. AlertRule Hook 接口设计

  **What to do**:
  - 创建 `engine/alert_rules.py`（告警规则 Hook 定义）
  - 定义 `AlertRule(PluginBase)` ABC：
    - `manifest.plugin_type` 固定为 `"alert"`
    - `severity: str` — critical / warning / info
    - `category: str` — optical / error / compliance / system
    - `evaluate(ifaces: List[Dict], device_rows: List[Dict]) -> List[AlertItem]` — 核心方法
    - `supports(device_model: str = None) -> bool` — 是否适用于某型号（默认全部支持）
  - 定义 `AlertItem` dataclass（从 `engine/report.py` 搬过来，保持兼容）：
    - `device_ip: str`
    - `device_name: str`
    - `category: str`
    - `severity: str`
    - `message: str`
    - `detail: str = ""`
  - 创建 `plugins/alerts/` 目录 + `__init__.py`
  - 写入 `tests/test_alert_rule_interface.py` — 测试：
    - AlertRule 不能直接实例化（ABC）
    - 子类必须实现 evaluate()
    - manifest.plugin_type 固定为 "alert"
    - supports() 默认返回 True

  **Must NOT do**:
  - 不在此任务实现任何具体告警规则（Task 10-13）
  - 不在此任务写 execute() 逻辑（Task 14）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 接口设计决定后续 4-5 个任务的形态，需要仔细权衡
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（Wave 3 的基石）
  - **Parallel Group**: Wave 3 (first)
  - **Blocks**: Task 10, 11, 12, 13, 14, 15
  - **Blocked By**: Task 3 (PluginManager), Task 5 (parser registry)

  **References**:
  - `engine/report.py:5-13` — AlertItem dataclass（搬移源）
  - `engine/report.py:71-141` — 现有 build_report() 的告警逻辑（理解 evaluate() 的输入输出）
  - `engine/plugin_base.py` — PluginBase 接口（继承基类）
  - `engine/report.py:46-48` — build_report 参数签名（理解 ifaces 和 device_rows 结构）

  **Acceptance Criteria**:
  - [ ] `engine/alert_rules.py` 包含 AlertRule ABC + AlertItem dataclass
  - [ ] `plugins/alerts/` 目录存在
  - [ ] `python3 -m pytest tests/test_alert_rule_interface.py -v` → PASS（≥ 3 个测试用例）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 子类必须实现 evaluate()
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.alert_rules import AlertRule
  class GoodAlert(AlertRule):
      severity = 'warning'
      category = 'optical'
      def evaluate(self, ifaces, device_rows):
          return []
  a = GoodAlert()
  assert a.supports() == True
  print('PASS: AlertRule subclass works')
  "
    Expected Result: "PASS: AlertRule subclass works"
    Failure Indicators: TypeError (ABC 阻止了实例化)
    Evidence: .omo/evidence/task-9-alert-interface.txt
  ```

  **Commit**: YES
  - Message: `feat(plugin): add AlertRule hook interface + AlertItem dataclass`
  - Files: `engine/alert_rules.py`, `plugins/alerts/__init__.py`, `tests/test_alert_rule_interface.py`

---

- [ ] 10. 光功率告警规则 (port from report.py)

  **What to do**:
  - 创建 `plugins/alerts/optical_power.py`
  - 实现 `OpticalPowerAlert(AlertRule)`:
    - `severity = "warning"`, `category = "optical"`
    - `evaluate()`:
      1. 遍历 ifaces 中有 `ddm_rx_power` 或 `RX 光功率(dBm)` 的行
      2. 从 `self.manifest` 的 `config` 中读取阈值（默认: warn=-15, crit=-20）
      3. 按阈值分类：
         - `rx < crit`: severity=critical
         - `rx < warn`: severity=warning
         - `rx >= warn`: 跳过（不产生告警）
      4. 返回 `AlertItem` 列表，同接口统计每个设备的异常数
    - YAML 模板（声明式配阈值）: 创建 `plugins/alerts/optical_power.template.yaml`
  - 写入 `tests/test_optical_power_alert.py` — TDD 先写测试：
    - 正常光功率 → 无告警
    - 功率低于 -15 → warning 告警
    - 功率低于 -20 → critical 告警
    - 无光模块 → 跳过（不误报）
    - 多设备混合场景

  **Must NOT do**:
  - 不在此任务调用 evaluate()（Task 14 统一执行）
  - 不修改 build_report()

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 复杂阈值判定逻辑 + 多分支覆盖
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11, 12, 13, 15)
  - **Blocks**: Task 14, 16
  - **Blocked By**: Task 9

  **References**:
  - `engine/report.py:71-79` — 现有光功率检查逻辑（搬移参考）
  - `engine/report.py:149-161` — 光模块健康统计（了解 overall 统计方式）
  - `engine/alert_rules.py` — AlertRule 基类（Task 9 产物）

  **Acceptance Criteria**:
  - [ ] `plugins/alerts/optical_power.py` 包含 OpticalPowerAlert
  - [ ] `python3 -m pytest tests/test_optical_power_alert.py -v` → PASS（≥ 5 个测试用例）
  - [ ] 告警结果与 `build_report()` 当前结果完全一致（见集成测试 Task 16）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 正常功率 → 无告警
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.optical_power import OpticalPowerAlert
  alert = OpticalPowerAlert()
  ifaces = [{'ddm_rx_power': '-8.5', '_device_ip': '10.0.0.1', '_device_name': 'sw1'}]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 0, f'Expected 0 alerts, got {len(results)}'
  print('PASS: healthy power → no alert')
  "
    Expected Result: "PASS: healthy power → no alert"
    Failure Indicators: AssertionError 或 KeyError
    Evidence: .omo/evidence/task-10-healthy.txt

  Scenario: 功率 < -15 → warning
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.optical_power import OpticalPowerAlert
  alert = OpticalPowerAlert()
  ifaces = [{'ddm_rx_power': '-17.0', '_device_ip': '10.0.0.2', '_device_name': 'sw2'}]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 1
  assert results[0].severity == 'warning'
  assert '光功率异常' in results[0].message
  print('PASS: low power → warning')
  "
    Expected Result: "PASS: low power → warning"
    Failure Indicators: AssertionError 或 severity 不对
    Evidence: .omo/evidence/task-10-warning.txt

  Scenario: 无光模块接口 → 跳过
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.optical_power import OpticalPowerAlert
  alert = OpticalPowerAlert()
  ifaces = [{'interface': 'Gi0/1', '_device_ip': '10.0.0.3'}]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 0
  print('PASS: no DDM field → skipped')
  "
    Expected Result: "PASS: no DDM field → skipped"
    Failure Indicators: AssertionError（误报）
    Evidence: .omo/evidence/task-10-no-ddm.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add OpticalPowerAlert plugin (ported from report.py)`
  - Files: `plugins/alerts/optical_power.py`, `plugins/alerts/optical_power.template.yaml`, `tests/test_optical_power_alert.py`

---

- [ ] 11. 错误计数告警规则

  **What to do**:
  - 创建 `plugins/alerts/error_counters.py`
  - 实现 `ErrorCounterAlert(AlertRule)`:
    - `severity = "warning"`, `category = "error"`
    - `evaluate()`:
      1. 遍历 ifaces 中错误计数字段：`undersize`, `oversize`, `collisions`, `fcs_err`, `crc_align_err`, `jabbers`
      2. 默认阈值: >100（可从 config 覆盖）
      3. 任一字段超阈值即产生告警
      4. 每个设备最多 1 条告警（含超阈值接口数）
  - 写入 `tests/test_error_counters_alert.py` — TDD：
    - 无错误 → 无告警
    - 单个接口 fcs_err=200 → 1 条告警
    - 2 个接口错误超标 → 1 条告警（含 "2 个接口"）
    - 错误值刚好 100 → 无告警（边界值）
    - 非数字字段 → 跳过（不崩溃）

  **Must NOT do**:
  - 不在此任务写 overall 统计逻辑

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 多字段遍历 + 聚合逻辑 + 边界条件
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 12, 13, 15)
  - **Blocks**: Task 14, 16
  - **Blocked By**: Task 9

  **References**:
  - `engine/report.py:82-92` — 现有错误计数检查逻辑（搬移参考）
  - `engine/alert_rules.py` — AlertRule 基类

  **Acceptance Criteria**:
  - [ ] `plugins/alerts/error_counters.py` 包含 ErrorCounterAlert
  - [ ] `python3 -m pytest tests/test_error_counters_alert.py -v` → PASS（≥ 5 个测试用例）
  - [ ] 结果与 build_report() error_alerts 一致

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 无错误 → 无告警
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.error_counters import ErrorCounterAlert
  alert = ErrorCounterAlert()
  ifaces = [{'interface': 'Gi0/1', '_device_ip': '10.0.0.1', 'fcs_err': '0', 'crc_align_err': '0'}]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 0
  print('PASS: clean counters → no alert')
  "
    Expected Result: "PASS: clean counters → no alert"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-11-clean.txt

  Scenario: 错误超标 → 1 条告警
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.error_counters import ErrorCounterAlert
  alert = ErrorCounterAlert()
  ifaces = [
      {'_device_ip': '10.0.0.1', '_device_name': 'sw1', 'fcs_err': '500', 'interface': 'Gi0/1'},
      {'_device_ip': '10.0.0.1', '_device_name': 'sw1', 'crc_align_err': '300', 'interface': 'Gi0/2'},
  ]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 1
  assert results[0].severity == 'warning'
  assert '2' in results[0].message  # 2 个接口
  print('PASS: error alert generated')
  "
    Expected Result: "PASS: error alert generated"
    Failure Indicators: AssertionError 或 severity/category 不符
    Evidence: .omo/evidence/task-11-alert.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add ErrorCounterAlert plugin`
  - Files: `plugins/alerts/error_counters.py`, `tests/test_error_counters_alert.py`

---

- [ ] 12. 风暴控制合规规则

  **What to do**:
  - 创建 `plugins/alerts/storm_control.py`
  - 实现 `StormControlAlert(AlertRule)`:
    - `severity = "info"`, `category = "compliance"`
    - `evaluate()`:
      1. 遍历 ifaces，检查 `storm_control` 字段
      2. 如果 `interface_mode == 'access'` 且 `storm_control` 不是 `yes`/`是`
      3. → 产生 compliance alert
      4. 统计每个设备缺少风暴控制的 access 端口数
  - 写入 `tests/test_storm_control_alert.py` — TDD：
    - access 口 + 风暴控制已开启 → 无告警
    - access 口 + 风暴控制未开启 → 1 条告警
    - trunk 口 + 无风暴控制 → 无告警（只检查 access）
    - 多个 access 口未开启 → 1 条告警（含端口数）

  **Must NOT do**:
  - 不实现更多合规规则（如 SSH/密码复杂度等，后续迭代）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 合规判定逻辑 + 端口类型过滤
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 13, 15)
  - **Blocks**: Task 14, 16
  - **Blocked By**: Task 9

  **References**:
  - `engine/report.py:94-100` — 现有 storm_control 检查逻辑（搬移参考）
  - `engine/alert_rules.py` — AlertRule 基类

  **Acceptance Criteria**:
  - [ ] `plugins/alerts/storm_control.py` 包含 StormControlAlert
  - [ ] `python3 -m pytest tests/test_storm_control_alert.py -v` → PASS（≥ 4 个测试用例）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: access 口无风暴控制 → alert
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.storm_control import StormControlAlert
  alert = StormControlAlert()
  ifaces = [
      {'_device_ip': '10.0.0.1', '_device_name': 'sw1',
       'interface_mode': 'access', 'storm_control': 'no', 'interface': 'Gi0/1'},
  ]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 1
  assert results[0].category == 'compliance'
  assert '风暴控制' in results[0].message
  print('PASS: storm control missing → alert')
  "
    Expected Result: "PASS: storm control missing → alert"
    Failure Indicators: AssertionError 或 category 不对
    Evidence: .omo/evidence/task-12-storm-alert.txt

  Scenario: trunk 口无风暴控制 → 跳过
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.storm_control import StormControlAlert
  alert = StormControlAlert()
  ifaces = [
      {'_device_ip': '10.0.0.1', '_device_name': 'sw1',
       'interface_mode': 'trunk', 'storm_control': 'no', 'interface': 'Gi0/2'},
  ]
  results = alert.evaluate(ifaces, [])
  assert len(results) == 0
  print('PASS: trunk port skipped')
  "
    Expected Result: "PASS: trunk port skipped"
    Failure Indicators: AssertionError（误报）
    Evidence: .omo/evidence/task-12-trunk-skip.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add StormControlAlert compliance plugin`
  - Files: `plugins/alerts/storm_control.py`, `tests/test_storm_control_alert.py`

---

- [ ] 13. 系统健康告警规则

  **What to do**:
  - 创建 `plugins/alerts/system_health.py`
  - 实现 `SystemHealthAlert(AlertRule)`:
    - `severity = "info"`, `category = "system"`
    - `evaluate()`:
      1. 统计每个设备的 up/down 接口数
      2. 如果设备接口 > 10 且 down 率 > 85% → 产生告警
      3. 阈值可配置: `min_interfaces=10, down_ratio=0.85`
  - 写入 `tests/test_system_health_alert.py` — TDD：
    - 100% up → 无告警
    - 12 口设备 11 down → alert (>85%)
    - 5 口设备 5 down → 无告警 (不满足最小接口数)
    - 12 口设备 9 down → 无告警 (刚好 75% < 85%)

  **Must NOT do**:
  - 不在此规则中添加风扇/温度/电源检查（后续迭代）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 比率计算 + 多条件判定
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 15)
  - **Blocks**: Task 14, 16
  - **Blocked By**: Task 9

  **References**:
  - `engine/report.py:142-147` — 现有系统健康检查逻辑
  - `engine/report.py:66-68` — 设备接口统计方式
  - `engine/alert_rules.py` — AlertRule 基类

  **Acceptance Criteria**:
  - [ ] `plugins/alerts/system_health.py` 包含 SystemHealthAlert
  - [ ] `python3 -m pytest tests/test_system_health_alert.py -v` → PASS（≥ 4 个测试用例）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 高 down 率 → alert
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.system_health import SystemHealthAlert
  alert = SystemHealthAlert()
  ifaces = []
  for i in range(12):
      ifaces.append({'_device_ip': '10.0.0.1', '_device_name': 'sw1',
                     'interface': f'Gi0/{i+1}', 'status': 'down' if i < 11 else 'up'})
  results = alert.evaluate(ifaces, [])
  assert len(results) == 1
  assert results[0].category == 'system'
  assert '85' in results[0].message or '91' in results[0].message  # 11/12 = 91%
  print('PASS: high down ratio → alert')
  "
    Expected Result: "PASS: high down ratio → alert"
    Failure Indicators: AssertionError
    Evidence: .omo/evidence/task-13-high-down.txt

  Scenario: 低接口数 → 跳过
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.system_health import SystemHealthAlert
  alert = SystemHealthAlert()
  ifaces = [{'_device_ip': '10.0.0.1', '_device_name': 'sw1',
            'interface': 'Gi0/1', 'status': 'down'}] * 5
  results = alert.evaluate(ifaces, [])
  assert len(results) == 0
  print('PASS: low interface count → skipped')
  "
    Expected Result: "PASS: low interface count → skipped"
    Failure Indicators: AssertionError（误报）
    Evidence: .omo/evidence/task-13-low-count.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add SystemHealthAlert plugin`
  - Files: `plugins/alerts/system_health.py`, `tests/test_system_health_alert.py`

---

- [ ] 14. AlertPluginManager + 规则执行引擎

  **What to do**:
  - 创建 `engine/alert_manager.py`
  - 实现 `AlertPluginManager`:
    - 继承/使用 `PluginManager` 的注册表
    - `load_alerts(alert_dirs: List[str])` — 扫描 `plugins/alerts/` + 额外目录
    - `evaluate_all(ifaces: List[Dict], device_rows: List[Dict]) -> List[AlertItem]`:
      1. 获取所有 `plugin_type == "alert"` 的插件
      2. 拓扑排序
      3. 逐个调用 `evaluate()`，隔离异常
      4. 聚合所有 `AlertItem`
    - `report_by_severity(alerts: List[AlertItem]) -> Dict[str, int]` — 按 severity 统计
    - `report_by_category(alerts: List[AlertItem]) -> Dict[str, int]` — 按 category 统计
  - 写入 `tests/test_alert_manager.py` — TDD：
    - load_alerts 加载正确数量
    - evaluate_all 聚合多个插件的告警
    - 一个插件崩不影响其他
    - topological_order 正确处理 alert 插件依赖
    - report_by_severity/category 统计正确

  **Must NOT do**:
  - 不在 AlertPluginManager 中耦合 FastAPI

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 编排逻辑 + 聚合 + 异常隔离 + 统计，复杂度高
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after plugin implementations)
  - **Blocks**: Task 16
  - **Blocked By**: Task 3, 9, 10, 11, 12, 13

  **References**:
  - `engine/plugin_manager.py` — PluginManager（基座）
  - `engine/alert_rules.py` — AlertRule 接口
  - `engine/report.py:122-147` — 现有告警生成逻辑（参考聚合方式）
  - `plugins/alerts/optical_power.py` — 一个具体规则实现（测试集成时用）

  **Acceptance Criteria**:
  - [ ] `engine/alert_manager.py` 包含 AlertPluginManager
  - [ ] `python3 -m pytest tests/test_alert_manager.py -v` → PASS（≥ 6 个测试用例）
  - [ ] evaluate_all() 异常隔离: 3 个 alert 插件中 1 个崩 → 另 2 个的告警正常返回

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: evaluate_all 聚合所有告警
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.alert_manager import AlertPluginManager
  from plugins.alerts.optical_power import OpticalPowerAlert
  from engine.alert_rules import AlertItem

  mgr = AlertPluginManager()
  mgr.register(OpticalPowerAlert())

  ifaces = [{'ddm_rx_power': '-25.0', '_device_ip': '10.0.0.1', '_device_name': 'sw1'}]
  results = mgr.evaluate_all(ifaces, [])
  assert len(results) == 1
  assert results[0].severity == 'critical'
  stats = mgr.report_by_severity(results)
  assert stats.get('critical', 0) == 1
  print('PASS: evaluate_all + stats work')
  "
    Expected Result: "PASS: evaluate_all + stats work"
    Failure Indicators: AssertionError 或 KeyError
    Evidence: .omo/evidence/task-14-evaluate-all.txt

  Scenario: 一个插件异常不影响其他
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.alert_manager import AlertPluginManager
  from engine.alert_rules import AlertRule, AlertItem
  from engine.plugin_base import PluginManifest

  class GoodAlert(AlertRule):
      severity = 'info'; category = 'system'
      def evaluate(self, ifaces, device_rows): return [AlertItem(device_ip='x', device_name='y', category=self.category, severity=self.severity, message='ok')]

  class BadAlert(AlertRule):
      severity = 'info'; category = 'system'
      def evaluate(self, ifaces, device_rows): raise RuntimeError('boom')

  mgr = AlertPluginManager()
  mgr.register(GoodAlert())
  mgr.register(BadAlert())
  results = mgr.evaluate_all([], [])
  assert len(results) == 1  # only GoodAlert's result
  assert results[0].message == 'ok'
  print('PASS: bad plugin isolated')
  "
    Expected Result: "PASS: bad plugin isolated"
    Failure Indicators: 未捕获 RuntimeError
    Evidence: .omo/evidence/task-14-isolation.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add AlertPluginManager with evaluate_all, statistics, error isolation`
  - Files: `engine/alert_manager.py`, `tests/test_alert_manager.py`

---

- [ ] 15. 告警 YAML 模板 (低代码方式配阈值)

  **What to do**:
  - 创建 `templates/alerts.template.yaml` — 项目级告警配置 YAML
  - 支持声明式配阈值，无需写 Python：
    ```yaml
    alerts:
      optical_power:
        enabled: true
        thresholds:
          warning_dbm: -15.0
          critical_dbm: -20.0
      error_counters:
        enabled: true
        thresholds:
          max_errors: 100
      storm_control:
        enabled: true
        check_access_only: true
      system_health:
        enabled: true
        min_interfaces: 10
        down_ratio: 0.85
    ```
  - 创建 `engine/alert_config.py` — YAML → Python 配置加载器：
    - `load_alert_config(path: str) -> Dict[str, Dict]`
    - 返回结构化配置，给 AlertPluginManager 注入
  - 写入 `tests/test_alert_config.py` — TDD：
    - YAML 解析正确 → 返回 Dict
    - 缺失文件 → 友好错误 + 返回默认值
    - 格式错误 → 清晰定位行号

  **Must NOT do**:
  - 不在 YAML 中定义告警逻辑（仅阈值和开关）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: YAML 读写 + 简单映射
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12, 13)
  - **Blocks**: Task 16
  - **Blocked By**: Task 9

  **References**:
  - `templates/textfsm_mapping.yaml` — 现有 YAML 配置风格
  - `engine/plugin_config.py` — TOML 加载模式（参考错误处理）
  - `engine/alert_rules.py` — 告警阈值字段名

  **Acceptance Criteria**:
  - [ ] `templates/alerts.template.yaml` 包含 4 个告警类型的配置示例
  - [ ] `engine/alert_config.py` 包含 load_alert_config()
  - [ ] `python3 -m pytest tests/test_alert_config.py -v` → PASS（≥ 3 个测试用例）

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 加载合法 YAML 配置
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.alert_config import load_alert_config
  config = load_alert_config('templates/alerts.template.yaml')
  assert 'alerts' in config
  assert 'optical_power' in config['alerts']
  assert config['alerts']['optical_power']['enabled'] == True
  print('PASS: alert config loaded')
  "
    Expected Result: "PASS: alert config loaded"
    Failure Indicators: KeyError 或 FileNotFoundError
    Evidence: .omo/evidence/task-15-config-load.txt

  Scenario: 缺失文件 → 友好错误
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.alert_config import load_alert_config
  config = load_alert_config('/nonexistent/alerts.yaml')
  assert isinstance(config, dict)  # 返回默认空配置
  print('PASS: missing file → graceful degradation')
  "
    Expected Result: "PASS: missing file → graceful degradation"
    Failure Indicators: FileNotFoundError 导致崩溃
    Evidence: .omo/evidence/task-15-missing-file.txt
  ```

  **Commit**: YES
  - Message: `feat(alerts): add YAML template for declarative threshold config`
  - Files: `templates/alerts.template.yaml`, `engine/alert_config.py`, `tests/test_alert_config.py`

---

- [ ] 16. 重构 build_report() 消费告警插件

  **What to do**:
  - 修改 `engine/report.py` 的 `build_report()`:
    - 不再内联光功率/错误计数/合规检查逻辑
    - 改为：创建 `AlertPluginManager` → `load_alerts()` → `evaluate_all(ifaces, device_rows)`
    - 将返回的 `AlertItem` 列表填入 `report.alerts`
    - 保留原有统计逻辑（`report.total_interfaces`、`report.up_interfaces` 等不变）
  - 修改 `main.py` 的 `/api/report`:
    - 将 `AlertPluginManager` 初始化移到 `lifespan` 或 `get_alert_manager()`
  - **关键**: 确保 `build_report()` 输出与重构前**完全一致**（同一输入 → 同一告警列表）
  - 写入 `tests/test_report_integration.py` — 集成测试：
    - 用真实日志样本（或 fixture 数据）验证 report 输出
    - 对比旧 build_report() 和新 build_report() 的 alerts 列表
    - 确保 alert 数量、severity、category 完全一致

  **Must NOT do**:
  - 不删除或修改 report.py 中不相关的统计逻辑
  - 不改变 /api/report 的 JSON 结构

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 集成改造 + 回归验证 + 风险最高
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO（最后集成点）
  - **Parallel Group**: Wave 4
  - **Blocks**: F1-F4
  - **Blocked By**: Task 10, 11, 12, 13, 14, 15

  **References**:
  - `engine/report.py:46-163` — 完整 build_report()（改造目标）
  - `engine/alert_manager.py` — AlertPluginManager API
  - `main.py:227-254` — /api/report 端点
  - `main.py:57-61` — FastAPI lifespan（全局初始化点）

  **Acceptance Criteria**:
  - [ ] `build_report()` 不再包含硬编码的告警逻辑
  - [ ] `python3 -m pytest tests/test_report_integration.py -v` → PASS
  - [ ] 相同 fixture 数据的 report.alerts 与重构前一致
  - [ ] `/api/report` 端点行为不变

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 重构前后告警结果一致
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from plugins.alerts.optical_power import OpticalPowerAlert
  from plugins.alerts.error_counters import ErrorCounterAlert
  from plugins.alerts.storm_control import StormControlAlert
  from plugins.alerts.system_health import SystemHealthAlert
  from engine.alert_manager import AlertPluginManager
  from engine.report import build_report

  mgr = AlertPluginManager()
  mgr.register(OpticalPowerAlert())
  mgr.register(ErrorCounterAlert())
  mgr.register(StormControlAlert())
  mgr.register(SystemHealthAlert())

  ifaces = [
      {'ddm_rx_power': '-18.0', 'fcs_err': '500', '_device_ip': '10.0.0.1',
       '_device_name': 'sw1', 'interface': 'Gi0/1', 'interface_mode': 'access',
       'storm_control': 'no', 'status': 'up'},
  ]
  report = build_report(ifaces, [], alert_manager=mgr)
  assert len(report.alerts) >= 3  # optical + error + compliance (system不一定触发)
  cats = {a.category for a in report.alerts}
  assert 'optical' in cats
  assert 'error' in cats
  assert 'compliance' in cats
  print(f'PASS: {len(report.alerts)} alerts generated via plugin system')
  "
    Expected Result: 输出 "PASS: N alerts generated via plugin system" (N ≥ 3)
    Failure Indicators: 告警数量不符，或 category 缺失
    Evidence: .omo/evidence/task-16-plugin-report.txt

  Scenario: /api/report 端点可用
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  # import 验证 build_report 无语法错误
  from engine.report import build_report
  # 无告警场景
  report = build_report([{'interface': 'Gi0/1', '_device_ip': '1.1.1.1'}], [])
  assert report.total_interfaces == 1
  print('PASS: build_report works with empty alerts')
  "
    Expected Result: "PASS: build_report works with empty alerts"
    Failure Indicators: ImportError 或 AttributeError
    Evidence: .omo/evidence/task-16-empty-report.txt
  ```

  **Commit**: YES
  - Message: `refactor(report): replace hardcoded alerts with pluggable AlertPluginManager`
  - Files: `engine/report.py`, `main.py`, `tests/test_report_integration.py`

---

- [ ] 17. Watchdog 热重载 (dev mode)

  **What to do**:
  - 创建 `engine/file_watcher.py`
  - 实现 `PluginWatcher`:
    - 用 `watchdog` 库监听 `plugins/` 目录变化（新增/修改/删除 .py 或 .toml 文件）
    - 变化时：重新调用 `PluginManager.load_all()`
    - 仅在 `--dev` 命令行参数或 `SWITCH_INSPECTOR_DEV=true` 环境变量下启用
    - 生产默认禁用
    - 通过 FastAPI `lifespan` 启动/停止 watcher（作为 background task）
  - 写入 `requirements.txt`：`watchdog>=6.0.0`（可选依赖，导入失败时降级）
  - 写入 `tests/test_file_watcher.py` — 模拟文件创建和插件重载

  **Must NOT do**:
  - 不在生产模式启 watchdog
  - 不自动重启 FastAPI 进程（只重载插件注册表）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: watch 标准库集成，简单文件监控
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 18, 19)
  - **Blocks**: None
  - **Blocked By**: Task 3

  **References**:
  - `main.py:57-61` — FastAPI lifespan（启动/停止点）
  - `main.py:257-260` — __main__ 入口（添加 --dev 参数处）
  - `engine/plugin_manager.py` — PluginManager.load_all()
  - 官方文档: `https://python-watchdog.readthedocs.io/` — watchdog API

  **Acceptance Criteria**:
  - [ ] `SWITCH_INSPECTOR_DEV=true python3 main.py` 启用 watchdog
  - [ ] 默认 `python3 main.py` 不启用
  - [ ] 新建 plugin 文件后自动重载

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: dev mode 启用 watchdog
    Tool: Bash
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. SWITCH_INSPECTOR_DEV=true python3 -c "
  from engine.file_watcher import PluginWatcher
  watcher = PluginWatcher(plugin_dirs=['plugins/alerts/'])
  assert watcher.enabled == True
  print('PASS: dev mode enables watcher')
  "
    Expected Result: "PASS: dev mode enables watcher"
    Failure Indicators: ImportError（watchdog 未安装）或 AssertionError
    Evidence: .omo/evidence/task-17-dev-mode.txt
  ```

  **Commit**: YES
  - Message: `feat(dev): add watchdog hot-reload for plugin directories`
  - Files: `engine/file_watcher.py`, `main.py`, `tests/test_file_watcher.py`

---

- [ ] 18. entry_points 发现支持

  **What to do**:
  - 在 `engine/plugin_manager.py` 的 `PluginManager` 新增方法：
    - `discover_entry_points(group: str = "switch_inspector.plugins") -> List[str]`
    - 使用 `importlib.metadata.entry_points(group=group)` 发现外部 pip 包插件
    - 对每个 entry point：`ep.load()` → 检查是否 PluginBase 子类 → `register()`
    - 加载失败的 entry point 记录 log warning，不阻断启动
  - 修改 `load_all()` 同时处理项目目录 + entry_points
  - 创建 `examples/external_plugin/` 示例项目：
    - `pyproject.toml` 声明 entry_point
    - 简单 `CustomAlert` 示例
  - 写入 `tests/test_entry_points.py` — mock entry_points 测试

  **Must NOT do**:
  - 不实现 entry_points 的版本约束（VPAT 后续迭代）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: importlib.metadata 标准库 API，简单
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 17, 19)
  - **Blocks**: None
  - **Blocked By**: Task 3

  **References**:
  - `engine/plugin_manager.py` — PluginManager 类（扩展目标）
  - 官方文档: `https://docs.python.org/3/library/importlib.metadata.html#entry-points`
  - `engine/plugin_base.py` — PluginBase（entry point load 后检查类型）

  **Acceptance Criteria**:
  - [ ] PluginManager.discover_entry_points() 实现
  - [ ] `examples/external_plugin/` 示例可安装和被发现
  - [ ] `python3 -m pytest tests/test_entry_points.py -v` → PASS

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: entry_points 发现逻辑可测试
    Tool: Bash (python3 -c)
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  from engine.plugin_manager import PluginManager
  pm = PluginManager()
  # 即使没有外部插件，也不应崩溃
  names = pm.discover_entry_points()
  assert isinstance(names, list)
  print(f'PASS: entry_points discovery returned {len(names)} plugins')
  "
    Expected Result: "PASS: entry_points discovery returned 0 plugins"
    Failure Indicators: ImportError 或 TypeError
    Evidence: .omo/evidence/task-18-entry-points.txt
  ```

  **Commit**: YES
  - Message: `feat(plugin): add entry_points discovery for pip-installable plugins`
  - Files: `engine/plugin_manager.py`, `examples/external_plugin/`, `tests/test_entry_points.py`

---

- [ ] 19. 插件接口规范文档

  **What to do**:
  - 创建 `docs/plugin-spec.md` — 完整的插件接口规范文档
  - 至少包含以下章节：
    1. **概述** — 插件系统设计理念、适用场景
    2. **快速开始** — 5 分钟创建第一个 alert 插件
    3. **插件类型** — parser / alert / compliance / processor / adapter 的接口定义
    4. **核心接口** — PluginBase、PluginManifest、PluginManager 的完整 API 参考
    5. **生命周期** — 加载 → 验证 → 注册 → 执行 → 卸载 的时序图/描述
    6. **配置系统** — plugin.toml schema、alerts.template.yaml 格式说明
    7. **分发方式** — 项目内目录 vs pip entry_points，各自的注册方法
    8. **容错策略** — 验证拒绝 / 运行时隔离 / 错误分级
    9. **热重载** — dev 模式 watchdog 使用方法
    10. **迁移指南** — 从旧 BaseParser 到新 PluginBase 的 step-by-step
    11. **附录** — 完整示例（alert 插件 ×2, parser 插件 ×1）
  - 文档质量要求：代码块可复制粘贴即运行，API 签名用 typing 标注

  **Must NOT do**:
  - 不添加不存在的 API（所有引用必须对应已实现代码）

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 技术文档，需要清晰的 API 说明和代码示例
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 17, 18)
  - **Blocks**: None
  - **Blocked By**: Task 4 (schema), 9 (alert interface), 14 (manager)

  **References**:
  - `engine/plugin_base.py` — 核心接口定义
  - `engine/plugin_manager.py` — PluginManager API
  - `engine/alert_rules.py` — AlertRule 接口
  - `plugins/alerts/optical_power.py` — 一个完整示例（用作附录）
  - `parsers/show_interfaces_transceiver.py` — parser 示例
  - `templates/plugin.example.toml` — 配置示例

  **Acceptance Criteria**:
  - [ ] `docs/plugin-spec.md` 包含全部 11 个章节
  - [ ] 至少 3 个可复制的完整代码示例
  - [ ] 所有 API 引用与实际代码一致

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 文档存在且包含核心章节
    Tool: Bash
    Steps:
      1. cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
      2. python3 -c "
  with open('docs/plugin-spec.md', 'r', encoding='utf-8') as f:
      content = f.read()
  assert '快速开始' in content or 'Quick Start' in content, 'Missing quick start'
  assert 'PluginBase' in content, 'Missing PluginBase reference'
  assert '生命周期' in content or 'Lifecycle' in content, 'Missing lifecycle'
  assert entry_points in content or 'entry point' in content, 'Missing entry_points'
  print(f'PASS: plugin-spec.md is {len(content)} chars, covers core topics')
  "
    Expected Result: "PASS: plugin-spec.md is NNNNN chars, covers core topics"
    Failure Indicators: FileNotFoundError 或 AssertionError
    Evidence: .omo/evidence/task-19-spec-doc.txt
  ```

  **Commit**: YES
  - Message: `docs: add plugin interface specification`
  - Files: `docs/plugin-spec.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `python3 -m pytest tests/ -v` + `python3 -c "import py_compile; ..."`. Review all changed files for: `except: pass`, `print()` in engine/, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: scan + preview + report full pipeline with real .log files. Test edge cases: empty log dir, no optical modules, all interfaces up.
  Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1** (Tasks 1-4): `test: add test framework + BaseParser tests`, `feat(plugin): ...`
- **Wave 2** (Tasks 5-8): `refactor(registry): ...`, `feat(parsers): ...`, `feat(parser): ...`, `feat(ui): ...`
- **Wave 3** (Tasks 9-15): `feat(plugin): add AlertRule hook interface`, `feat(alerts): ...` ×5, `feat(alerts): add AlertPluginManager`
- **Wave 4** (Tasks 16-19): `refactor(report): ...`, `feat(dev): ...`, `feat(plugin): ...`, `docs: ...`

---

## Success Criteria

### Verification Commands
```bash
# 全量测试
cd /mnt/c/Users/happy/Desktop/dev/switch-inspector
python3 -m pytest tests/ -v
# Expected: 所有测试通过 (≥ 60 个测试用例)

# 导入验证
python3 -c "from engine.plugin_base import PluginBase; from engine.alert_rules import AlertRule; from engine.plugin_manager import PluginManager; print('all imports OK')"

# 集成验证（需要日志目录）
python3 -c "
from engine.registry import PluginAwareParserRegistry
from engine.alert_manager import AlertPluginManager
reg = PluginAwareParserRegistry()
reg.initialize()
print(f'parsers: {len(reg._custom_parsers)} loaded')
mgr = AlertPluginManager()
mgr.load_alerts(['plugins/alerts/'])
print(f'alerts: {len(mgr.get_plugins(\"alert\"))} loaded')
"
```

### Final Checklist
- [ ] 所有 "Must Have" 有对应实现
- [ ] 所有 "Must NOT Have" 未出现在代码中
- [ ] 19 个实现任务全部完成
- [ ] F1-F4 四审全部 APPROVE
- [ ] 用户明确 "okay"
