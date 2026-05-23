from engine.parser_base import FixedWidthTableParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesUsage(FixedWidthTableParser):
    command = "show interfaces usage"
    columns = ["interface", "bandwidth", "avg_usage", "in_usage", "out_usage"]

    fields = [
        FieldDef(key="interface", label="接口名", category="interface"),
        FieldDef(key="bandwidth", label="带宽", category="interface"),
        FieldDef(key="avg_usage", label="平均利用率", category="interface"),
        FieldDef(key="in_usage", label="入利用率", category="interface"),
        FieldDef(key="out_usage", label="出利用率", category="interface"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = self._parse_table(raw, self.columns)
        for row in result.rows:
            row['normalized_iface'] = normalize_iface(row.get('interface', ''))
            row['category'] = 'interface'
        return result
