from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class AlertItem:
    device_ip: str
    device_name: str
    category: str  # optical / error / compliance / system
    severity: str  # critical / warning / info
    message: str
    detail: str = ""


@dataclass
class DeviceSummary:
    ip: str
    name: str
    model: str
    serial: str
    sw_version: str
    interface_count: int
    up_count: int
    down_count: int
    optical_count: int
    optical_alert_count: int
    error_alert_count: int
    compliance_issues: int


@dataclass
class Report:
    scan_time: str = ""
    scan_path: str = ""
    total_devices: int = 0
    total_interfaces: int = 0
    up_interfaces: int = 0
    down_interfaces: int = 0
    optical_healthy: int = 0
    optical_warning: int = 0
    optical_critical: int = 0
    devices: List[DeviceSummary] = field(default_factory=list)
    alerts: List[AlertItem] = field(default_factory=list)


def build_report(ifaces: List[Dict],
                 device_rows: List[Dict] = None,
                 parsed_data: Dict[str, List[Dict]] = None) -> Report:
    report = Report()
    systems = (parsed_data or {}).get('system', [])

    # Group interface rows by device
    dev_ifaces: Dict[str, List[Dict]] = {}
    for row in ifaces:
        ip = row.get('_device_ip', '')
        dev_ifaces.setdefault(ip, []).append(row)

    # Build device summaries
    device_map = {}
    for dr in device_rows or []:
        ip = dr.get('_device_ip', '')
        if ip:
            device_map[ip] = dr

    for ip, iface_list in dev_ifaces.items():
        dev_info = device_map.get(ip, {})
        up = sum(1 for r in iface_list if r.get('status') == 'up')
        down = sum(1 for r in iface_list if r.get('status') == 'down')
        optical = sum(1 for r in iface_list if r.get('transceiver_present') == '是'
                      or r.get('ddm_present') == '是')

        # Check optical power
        optical_alerts = 0
        for r in iface_list:
            rx = r.get('ddm_rx_power', '') or r.get('RX 光功率(dBm)', '')
            try:
                if rx and float(rx) < -15:
                    optical_alerts += 1
            except ValueError:
                pass

        # Check error counters
        error_alerts = 0
        for r in iface_list:
            for ef in ['undersize', 'oversize', 'collisions', 'fcs_err',
                       'crc_align_err', 'jabbers']:
                try:
                    if r.get(ef) and int(r[ef]) > 100:
                        error_alerts += 1
                        break
                except (ValueError, TypeError):
                    pass

        # Compliance issues
        compliance = 0
        for r in iface_list:
            if r.get('storm_control') not in ('yes', '是'):
                if r.get('interface_mode') == 'access':
                    compliance += 1

        ds = DeviceSummary(
            ip=ip,
            name=dev_info.get('_device_name', ''),
            model=dev_info.get('system_description', '')[:30],
            serial=dev_info.get('system_serial_number', ''),
            sw_version=dev_info.get('system_software_version', ''),
            interface_count=len(iface_list),
            up_count=up, down_count=down,
            optical_count=optical,
            optical_alert_count=optical_alerts,
            error_alert_count=error_alerts,
            compliance_issues=compliance,
        )
        report.devices.append(ds)

        report.total_interfaces += len(iface_list)
        report.up_interfaces += up
        report.down_interfaces += down

    report.total_devices = len(report.devices)

    # Generate alerts
    for ds in report.devices:
        if ds.optical_alert_count > 0:
            report.alerts.append(AlertItem(
                device_ip=ds.ip, device_name=ds.name,
                category='optical', severity='warning',
                message=f"{ds.optical_alert_count} 个接口光功率异常",
            ))
        if ds.error_alert_count > 0:
            report.alerts.append(AlertItem(
                device_ip=ds.ip, device_name=ds.name,
                category='error', severity='warning',
                message=f"{ds.error_alert_count} 个接口错误计数超标",
            ))
        if ds.compliance_issues > 0:
            report.alerts.append(AlertItem(
                device_ip=ds.ip, device_name=ds.name,
                category='compliance', severity='info',
                message=f"{ds.compliance_issues} 个接口缺少风暴控制",
            ))
        if ds.interface_count > 10 and ds.down_count > ds.interface_count * 0.85:
            report.alerts.append(AlertItem(
                device_ip=ds.ip, device_name=ds.name,
                category='system', severity='info',
                message=f"{ds.down_count}/{ds.interface_count} 接口down ({(ds.down_count*100)//ds.interface_count}%)",
            ))

    # Optical health summary
    for iface in ifaces:
        rx = iface.get('ddm_rx_power', '') or iface.get('RX 光功率(dBm)', '')
        try:
            val = float(rx)
            if val < -20:
                report.optical_critical += 1
            elif val < -15:
                report.optical_warning += 1
            else:
                report.optical_healthy += 1
        except (ValueError, TypeError):
            pass

    return report
