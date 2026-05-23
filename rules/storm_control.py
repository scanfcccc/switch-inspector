from typing import List

from engine.alert_rule_base import AlertRule, AlertResult, AlertSeverity


class StormControlRule(AlertRule):
    """风暴控制合规检查规则。

    扫描每个接口的 storm_control / broadcast_suppression 字段，
    如果风暴控制缺失或处于关闭状态则产生 CRITICAL 告警。

    Config 支持:
      - required (bool, 默认 True): 设为 False 则跳过检查
      - strict   (bool, 默认 True):
          True  → 缺少字段即视为违规
          False → 仅当字段存在且显式关闭时才告警
    """

    name = "storm_control"
    description = "风暴控制合规检查"

    # ── 公用：提取接口名称 ──

    @staticmethod
    def _get_ifname(iface: dict) -> str:
        return str(iface.get("name") or iface.get("interface") or "")

    # ── 公用：风暴控制值判断 ──

    @staticmethod
    def _is_enabled(value) -> bool:
        """判断风暴控制相关字段值是否为「已开启」状态。

        支持的格式:
          - bool:   True / False
          - str:    "enable" / "disable", "enabled" / "disabled",
                    "yes" / "no", "是" / "否", "1" / "0", "true" / "false"
          - int:    1 / 0
          - float:  1.0 / 0.0
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in (
                "enable", "enabled", "yes", "是", "1", "true",
            )
        return False

    @staticmethod
    def _has_storm_key(iface: dict) -> bool:
        """接口字典中是否存在风暴控制相关字段。"""
        return "storm_control" in iface or "broadcast_suppression" in iface

    # ── 核心评估方法 ──

    def evaluate(self, device_data: dict) -> List[AlertResult]:
        config = self.config or {}
        required = config.get("required", True)
        strict = config.get("strict", True)

        # required=False: 完全跳过检查
        if not required:
            return []

        results: List[AlertResult] = []
        interfaces: List[dict] = device_data.get("interfaces") or []
        device_ip: str = device_data.get("device_ip", "") or ""

        # 没有任何接口包含风暴控制数据 → 设备级 INFO 提示
        has_any_storm_data = any(self._has_storm_key(iface) for iface in interfaces)
        if not has_any_storm_data:
            results.append(AlertResult(
                rule_name=self.name,
                severity=AlertSeverity.INFO,
                message="设备未提供风暴控制数据，无法检查风暴控制合规性",
                device_ip=device_ip,
            ))
            return results

        # 逐接口扫描
        for iface in interfaces:
            if_name = self._get_ifname(iface)

            # 检查 storm_control 字段
            sc = iface.get("storm_control")
            if sc is not None:
                if self._is_enabled(sc):
                    continue  # 已开启 → 合规
                # 显式关闭 → 告警
                results.append(AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.CRITICAL,
                    message=f"接口 {if_name} 风暴控制未开启 (storm_control={sc!r})",
                    device_ip=device_ip,
                    interface=if_name,
                    details={"field": "storm_control", "value": sc},
                ))
                continue

            # 检查 broadcast_suppression 字段
            bs = iface.get("broadcast_suppression")
            if bs is not None:
                if self._is_enabled(bs):
                    continue  # 已开启 → 合规
                results.append(AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.CRITICAL,
                    message=f"接口 {if_name} 风暴控制未开启 (broadcast_suppression={bs!r})",
                    device_ip=device_ip,
                    interface=if_name,
                    details={"field": "broadcast_suppression", "value": bs},
                ))
                continue

            # 两个字段都不存在
            if strict:
                results.append(AlertResult(
                    rule_name=self.name,
                    severity=AlertSeverity.CRITICAL,
                    message=f"接口 {if_name} 缺少风暴控制配置",
                    device_ip=device_ip,
                    interface=if_name,
                    details={"field": None, "value": None, "reason": "missing_key"},
                ))
            # strict=False 时，缺少字段不视为违规，不做任何事

        return results
