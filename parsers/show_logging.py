import re
from engine.parser_base import BaseParser, FieldDef, ParseResult


class ShowLogging(BaseParser):
    command = "show logging"
    fields = [
        FieldDef(key="log_timestamp", label="日志时间", category="log"),
        FieldDef(key="log_facility", label="日志Facility", category="log"),
        FieldDef(key="log_severity", label="日志级别", category="log"),
        FieldDef(key="log_message", label="日志内容", category="log"),
        FieldDef(key="log_sequence", label="日志序号", category="log"),
    ]

    LOG_LINE = re.compile(
        r'^(?:(\d{6}):\s+)?\*?(?P<timestamp>\w+\s+\d+\s+\d{2}:\d{2}:\d{2}):\s+'
        r'(?P<message>.*)$'
    )

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        in_log_buffer = False
        for line in raw.split('\n'):
            stripped = line.strip()
            if 'Log Buffer' in stripped:
                in_log_buffer = True
                continue
            if not in_log_buffer:
                continue
            if not stripped:
                continue
            if stripped.startswith('PJXRMYY') or '#' in stripped:
                continue

            m = self.LOG_LINE.match(stripped)
            if m:
                seq = m.group(1) if m.group(1) else ''
                ts = m.group('timestamp')
                msg = m.group('message')

                fac_sev = ''
                content = msg
                fac_m = re.match(r'%([A-Za-z_]+)-(\d)-([A-Za-z_]+):\s*(.*)', msg)
                if fac_m:
                    fac_sev = f"{fac_m.group(1)}/{fac_m.group(3)}"
                    content = fac_m.group(4)

                result.rows.append({
                    'log_sequence': seq,
                    'log_timestamp': ts,
                    'log_facility': fac_sev,
                    'log_severity': seq or fac_sev.split('/')[-1] if '/' in fac_sev else '',
                    'log_message': content,
                    'category': 'log',
                })

        return result
