from engine.parser_base import FixedWidthTableParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesDescription(FixedWidthTableParser):
    command = "show interfaces description"
    columns = ["interface", "status", "admin_status", "description"]

    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="status", label="状态", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="admin_status", label="管理状态", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="description", label="描述", category="interface",
                 join_group="interface", join_key="normalized_iface"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = self._parse_table(raw, self.columns)
        for row in result.rows:
            row['normalized_iface'] = normalize_iface(row.get('interface', ''))
            row['category'] = 'interface'
        return result


class ShowInterfacesStatus(FixedWidthTableParser):
    command = "show interfaces status"
    columns = ["interface", "status", "vlan", "duplex", "speed", "type"]
    fields = [
        FieldDef(key="interface", label="接口名", category="interface"),
        FieldDef(key="status", label="接口状态", category="interface"),
        FieldDef(key="vlan", label="接口VLAN", category="interface"),
        FieldDef(key="duplex", label="双工模式", category="interface"),
        FieldDef(key="speed", label="速率", category="interface"),
        FieldDef(key="type", label="接口类型", category="interface"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = self._parse_table(raw, self.columns)
        for row in result.rows:
            row['normalized_iface'] = normalize_iface(row.get('interface', ''))
            row['category'] = 'interface'
        return result
