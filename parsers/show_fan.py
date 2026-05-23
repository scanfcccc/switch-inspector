from engine.parser_base import FixedWidthTableParser, FieldDef, ParseResult


class ShowFanSpeed(FixedWidthTableParser):
    command = "show fan speed"
    columns = ["fan_id", "fan_type", "status", "speed", "speed_level"]
    _key_rename = {"status": "fan_status", "speed": "fan_speed", "speed_level": "fan_speed_level"}

    fields = [
        FieldDef(key="fan_id", label="风扇ID", category="system"),
        FieldDef(key="fan_type", label="风扇类型", category="system"),
        FieldDef(key="fan_status", label="风扇状态", category="system"),
        FieldDef(key="fan_speed", label="风扇转速", category="system"),
        FieldDef(key="fan_speed_level", label="风扇级别", category="system"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = self._parse_table(raw, self.columns)
        for row in result.rows:
            for old_k, new_k in self._key_rename.items():
                if old_k in row:
                    row[new_k] = row.pop(old_k)
            row['category'] = 'system'
        return result
