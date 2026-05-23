import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable


@dataclass
class FieldDef:
    key: str
    label: str
    category: str  # device / interface / neighbor / system / log
    join_group: Optional[str] = None  # interface / neighbor / device / None
    join_key: Optional[str] = None    # normalized_iface / device_ip / None
    dtype: str = "str"                # str / int / float / bool
    description: str = ""


@dataclass
class ParseResult:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseParser(ABC):
    command: str = ""
    fields: List[FieldDef] = []

    @abstractmethod
    def parse(self, raw: str) -> ParseResult:
        ...


class TableParser(BaseParser):
    skip_header: int = 1
    columns: List[str] = []
    sep: str = r'\s{2,}'  # split by 2+ spaces

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        lines = raw.strip().split('\n')
        lines = [l for l in lines if l.strip()]
        for i, line in enumerate(lines):
            if i < self.skip_header:
                continue
            if self._is_separator(line):
                continue
            parts = re.split(self.sep, line.strip())
            if len(parts) != len(self.columns):
                # try whitespace split as fallback
                parts = line.strip().split()
                if len(parts) != len(self.columns):
                    result.errors.append(f"Row {i}: column mismatch "
                        f"(expected {len(self.columns)}, got {len(parts)}): {line[:60]}")
                    continue
            row = {}
            for j, col in enumerate(self.columns):
                row[col] = parts[j].strip()
            result.rows.append(row)
        return result

    def _is_separator(self, line: str) -> bool:
        return all(c in '- ' for c in line)


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
            parts = re.split(self.separator, line, maxsplit=1)
            if len(parts) == 2:
                key = parts[0].strip().lower().replace(' ', '_')
                value = parts[1].strip()
                row[key] = value
        if row:
            result.rows.append(row)
        return result


class BlockParser(BaseParser):
    block_delimiter: str = r'=======+Interface\s+\S+\s+\S+========'

    def parse_blocks(self, raw: str) -> List[Dict[str, str]]:
        blocks = re.split(self.block_delimiter, raw)
        result = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            kv = {}
            for line in block.split('\n'):
                line = line.strip()
                if not line or re.match(r'^[-=\s]+$', line):
                    continue
                if ':' in line:
                    k, v = line.split(':', 1)
                    kv[k.strip()] = v.strip()
            if kv:
                result.append(kv)
        return result
