from engine.parser_base import KVPParser, FieldDef, ParseResult


class ShowVersion(KVPParser):
    command = "show version"
    separator = r'\s+:\s+'

    fields = [
        FieldDef(key="system_description", label="系统描述", category="device",
                 join_group="device", join_key="device_ip", description="交换机型号描述"),
        FieldDef(key="system_start_time", label="启动时间", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_uptime", label="运行时长", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_hardware_version", label="硬件版本", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_software_version", label="软件版本", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_serial_number", label="序列号", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_patch_number", label="补丁版本", category="device",
                 join_group="device", join_key="device_ip"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = super().parse(raw)
        for row in result.rows:
            row['category'] = 'device'
        return result


class ShowVersionDetail(KVPParser):
    command = "show version detail"
    fields = ShowVersion.fields + [
        FieldDef(key="system_software_number", label="软件编号", category="device",
                 join_group="device", join_key="device_ip"),
        FieldDef(key="system_core_version", label="内核版本", category="device",
                 join_group="device", join_key="device_ip"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = super().parse(raw)
        for row in result.rows:
            row['category'] = 'device'
        return result
