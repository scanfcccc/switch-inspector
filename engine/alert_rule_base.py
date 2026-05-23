from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, ClassVar, Optional
from abc import abstractmethod

from engine.plugin_base import PluginBase


class AlertSeverity(Enum):
    """告警严重等级 — 数值越大越严重。"""
    INFO = 1
    WARNING = 2
    CRITICAL = 3


@dataclass
class AlertResult:
    """一条告警结果。"""
    rule_name: str
    severity: AlertSeverity
    message: str
    device_ip: Optional[str] = None
    interface: Optional[str] = None
    details: Optional[Dict] = None


class AlertRule(PluginBase):
    """告警规则插件基类。

    所有告警规则必须继承此类并实现:
      - name          (ClassVar[str])
      - description   (ClassVar[str])
      - evaluate()    (抽象方法)

    可选的类变量:
      - severity      (ClassVar[AlertSeverity], 默认 WARNING)
      - config        (实例级配置字典, 默认 {})
    """

    # ── 子类必须定义的类变量 ──
    name: ClassVar[str]
    description: ClassVar[str]

    # ── 带默认值的类变量 ──
    severity: ClassVar[AlertSeverity] = AlertSeverity.WARNING
    no_auto_register: ClassVar[bool] = True

    # ── 实例级配置（从 YAML 加载） ──
    config: dict = {}

    @abstractmethod
    def evaluate(self, device_data: dict) -> List[AlertResult]:
        """评估设备数据并返回告警列表。

        Args:
            device_data: 完整解析后的设备数据字典，包含
                device_ip, device_name, interfaces, device_info 等字段。

        Returns:
            告警结果列表（可能为空）。
        """
        ...

    def validate(self) -> List[str]:
        """校验配置有效性。"""
        errors = super().validate()
        try:
            name = type(self).name
            if not name:
                errors.append("AlertRule subclass must define a non-empty 'name'")
        except AttributeError:
            errors.append("AlertRule subclass must define 'name'")

        try:
            desc = type(self).description
            if not desc:
                errors.append("AlertRule subclass must define a non-empty 'description'")
        except AttributeError:
            errors.append("AlertRule subclass must define 'description'")

        return errors
