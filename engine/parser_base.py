import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, ClassVar


@dataclass
class FieldDef:
    key: str
    label: str
    category: str
    join_group: Optional[str] = None
    join_key: Optional[str] = None
    dtype: str = "str"
    description: str = ""


@dataclass
class ParseResult:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseParser(ABC):
    command: str = ""
    fields: List[FieldDef] = []
    version: ClassVar[str] = "1.0.0"

    @abstractmethod
    def parse(self, raw: str) -> ParseResult:
        ...

    def validate(self) -> List[str]:
        return []

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        try:
            from engine.plugin_manager import _INSTANCE
        except ImportError:
            pass


class FixedWidthTableParser(BaseParser):
    """
    Parse fixed-width tables from switch CLI output.
    Column widths are determined by the separator line (----).
    """
    def _get_column_spans(self, separator_line: str) -> List[tuple]:
        spans = []
        i = 0
        while i < len(separator_line):
            if separator_line[i] == ' ':
                i += 1
                continue
            start = i
            while i < len(separator_line) and separator_line[i] != ' ':
                i += 1
            end = i
            spans.append((start, end))
        return spans

    def _parse_table(self, raw: str, column_names: List[str],
                     min_width: int = 3) -> ParseResult:
        result = ParseResult()
        lines = raw.strip().split('\n')
        # skip header
        data_start = 0
        separator_line = None

        for i, line in enumerate(lines):
            if re.match(r'^[-\s]+$', line) and len(set(line.strip())) <= 2:
                separator_line = line
                data_start = i + 1
                break

        if not separator_line:
            # fallback: detect column boundaries from header
            for i, line in enumerate(lines):
                if i > 0 and re.match(r'^\s*[-\s]+\s*$', line):
                    separator_line = line
                    data_start = i + 1
                    break

        if not separator_line:
            # try to find dashed line
            for i, line in enumerate(lines):
                if '---' in line and not any(c.isalpha() for c in line):
                    separator_line = line
                    data_start = i + 1
                    break

        if not separator_line:
            return self._fallback_parse(lines, column_names)

        spans = self._get_column_spans(separator_line)

        if not spans or len(spans) != len(column_names):
            return self._fallback_parse(lines, column_names)

        for i in range(data_start, len(lines)):
            line = lines[i]
            if not line.strip() or re.match(r'^[-\s]+$', line):
                continue
            row = {}
            for ci, (s, e) in enumerate(spans):
                val = line[s:e].strip() if s < len(line) else ''
                if ci < len(column_names):
                    row[column_names[ci]] = val
            if any(v for v in row.values()):
                result.rows.append(row)

        return result

    def _fallback_parse(self, lines, column_names) -> ParseResult:
        result = ParseResult()
        for i, line in enumerate(lines):
            if not line.strip() or re.match(r'^[-\s]+$', line):
                continue
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= len(column_names):
                row = dict(zip(column_names, parts[:len(column_names)]))
                result.rows.append(row)
        for i, line in enumerate(lines):
            if not line.strip() or re.match(r'^[-\s]+$', line):
                continue
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) < len(column_names):
                result.errors.append(f"Row {i}: expected {len(column_names)} columns, got {len(parts)}")
        return result

    def parse(self, raw: str) -> ParseResult:
        return self._parse_table(raw, self.columns)


class KVPParser(BaseParser):
    separator: str = r'\s+:\s+'

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        row = {}
        for line in raw.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[-=\s]+$', line):
                continue
            if re.match(r'^[A-Za-z][A-Za-z\s]+\s{2,}$', line):
                continue
            parts = re.split(self.separator, line, maxsplit=1)
            if len(parts) == 2:
                key = parts[0].strip().lower().replace(' ', '_').replace('.', '')
                value = parts[1].strip()
                row[key] = value
        if row:
            result.rows.append(row)
        return result


class BlockParser(BaseParser):
    block_delimiter: str = r'^=======+Interface[ \t]+[^=\n]+========$'

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        blocks = re.split(f'({self.block_delimiter})', raw, flags=re.MULTILINE)
        if len(blocks) < 3:
            return result

        for i in range(1, len(blocks), 2):
            delimiter = blocks[i].strip()
            content = blocks[i + 1].strip() if i + 1 < len(blocks) else ''

            iface_match = re.search(r'Interface[ \t]+([^=\n]+[^=\s])', delimiter)
            iface_name = iface_match.group(1).strip() if iface_match else ''
            if not iface_name:
                continue

            row = {'interface': iface_name}
            if 'transceiver is absent' in content or "doesn't support DDM" in content:
                row['transceiver_present'] = '否'
            else:
                row['transceiver_present'] = '是'
                for cl in content.split('\n'):
                    cl = cl.strip()
                    if ':' in cl and not cl.startswith('=='):
                        k, v = cl.split(':', 1)
                        row[k.strip()] = v.strip()
            result.rows.append(row)
        return result
