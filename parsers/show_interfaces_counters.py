import re
from engine.parser_base import BaseParser, FixedWidthTableParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface


class ShowInterfacesCountersErrors(FixedWidthTableParser):
    command = "show interfaces counters errors"
    fields = [
        FieldDef(key="interface", label="接口名", category="interface"),
        FieldDef(key="undersize", label="UnderSize错误", category="interface", dtype="int"),
        FieldDef(key="oversize", label="OverSize错误", category="interface", dtype="int"),
        FieldDef(key="collisions", label="冲突", category="interface", dtype="int"),
        FieldDef(key="fragments", label="碎片", category="interface", dtype="int"),
        FieldDef(key="jabbers", label="Jabber错误", category="interface", dtype="int"),
        FieldDef(key="crc_align_err", label="CRC对齐错误", category="interface", dtype="int"),
        FieldDef(key="align_err", label="对齐错误", category="interface", dtype="int"),
        FieldDef(key="fcs_err", label="FCS错误", category="interface", dtype="int"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        # split into two tables at the double-header
        tables = re.split(r'\n(?=Interface\s+(?:Jabbers|UnderSize))', raw.strip())

        first_cols = ["interface", "undersize", "oversize", "collisions", "fragments"]
        second_cols = ["interface", "jabbers", "crc_align_err", "align_err", "fcs_err"]

        all_rows = {}

        for ti, (cols, label) in enumerate([(first_cols, "table1"), (second_cols, "table2")]):
            if ti >= len(tables):
                continue
            partial = self._parse_table(tables[ti], cols)
            for row in partial.rows:
                iface_short = row.get('interface', '')
                iface = normalize_iface(iface_short) if iface_short else ''
                row['normalized_iface'] = iface
                row['interface'] = iface
                row['category'] = 'interface'
                if iface in all_rows:
                    all_rows[iface].update(row)
                else:
                    all_rows[iface] = row

        result.rows = list(all_rows.values())
        return result


class ShowInterfacesCountersRate(FixedWidthTableParser):
    command = "show interfaces counters rate up"
    columns = ["interface", "sampling_time", "input_rate_bps", "input_rate_pps",
               "output_rate_bps", "output_rate_pps"]

    fields = [
        FieldDef(key="interface", label="接口名", category="interface"),
        FieldDef(key="input_rate_bps", label="入向速率(bps)", category="interface", dtype="int"),
        FieldDef(key="input_rate_pps", label="入向速率(pps)", category="interface", dtype="int"),
        FieldDef(key="output_rate_bps", label="出向速率(bps)", category="interface", dtype="int"),
        FieldDef(key="output_rate_pps", label="出向速率(pps)", category="interface", dtype="int"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = self._parse_table(raw, self.columns)
        for row in result.rows:
            iface = normalize_iface(row.get('interface', ''))
            row['normalized_iface'] = iface
            row['interface'] = iface
            row['category'] = 'interface'
        return result
