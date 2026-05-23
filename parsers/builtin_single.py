import re
from engine.parser_base import BaseParser, FieldDef, ParseResult


class ShowClock(BaseParser):
    command = "show clock"
    fields = [FieldDef(key="clock", label="系统时间", category="device",
                       join_group="device", join_key="device_ip")]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        line = raw.strip().split('\n')[0] if raw.strip() else ''
        if line:
            result.rows.append({'clock': line, 'category': 'device'})
        return result


class ShowException(BaseParser):
    command = "show exception"
    fields = [FieldDef(key="exception_info", label="异常信息", category="system")]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        line = raw.strip()
        if 'not any exception' in line.lower():
            result.rows.append({'exception_info': '无异常', 'category': 'system'})
        elif line:
            result.rows.append({'exception_info': line[:200], 'category': 'system'})
        return result


class ShowCoredumpFiles(BaseParser):
    command = "show coredump files"
    fields = [FieldDef(key="coredump_files", label="CoreDump文件数", category="system")]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        lines = [l for l in raw.strip().split('\n') if l.strip()]
        count = len(lines) - 1 if len(lines) > 1 else 0
        result.rows.append({'coredump_files': str(count), 'category': 'system'})
        return result


class ShowErps(BaseParser):
    command = "show erps"
    fields = [FieldDef(key="erps_status", label="ERPS状态", category="system")]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        m = re.search(r'Global Status\s+:\s+(\S+)', raw)
        result.rows.append({
            'erps_status': m.group(1) if m else 'N/A',
            'category': 'system',
        })
        return result


class ShowSwitchVirtualLink(BaseParser):
    command = "show switch virtual link port"
    fields = [FieldDef(key="switch_mode", label="交换机模式", category="system")]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        m = re.search(r'running in "(\S+)" mode', raw)
        result.rows.append({
            'switch_mode': m.group(1) if m else 'N/A',
            'category': 'system',
        })
        return result


class ShowPasswordPolicy(BaseParser):
    command = "show password policy"
    fields = [
        FieldDef(key="password_encryption", label="密码加密", category="system"),
        FieldDef(key="password_strong_check", label="强密码检查", category="system"),
        FieldDef(key="password_min_size", label="最小长度", category="system"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        row = {'category': 'system'}
        for line in raw.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                k = k.strip().lower().replace(' ', '_')
                v = v.strip()
                if 'encryption' in k: row['password_encryption'] = v
                elif 'strong' in k: row['password_strong_check'] = v
                elif 'min-size' in k or 'min_size' in k: row['password_min_size'] = v
        result.rows.append(row)
        return result


class ShowDhcpSnooping(BaseParser):
    command = "show ip dhcp snooping"
    fields = [
        FieldDef(key="dhcp_snooping_enabled", label="DHCP Snooping启用", category="system"),
        FieldDef(key="dhcp_snooping_trusted_interfaces", label="信任接口数", category="system"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        enabled = 'ENABLE' in raw
        trusted = len(re.findall(r'YES', raw))
        result.rows.append({
            'dhcp_snooping_enabled': '启用' if enabled else '禁用',
            'dhcp_snooping_trusted_interfaces': str(trusted),
            'category': 'system',
        })
        return result
