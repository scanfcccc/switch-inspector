import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class DeviceMeta:
    ip: str = ""
    name: str = ""
    serial: str = ""
    model: str = ""
    hw_version: str = ""
    sw_version: str = ""
    uptime: str = ""
    start_time: str = ""
    inspect_time: str = ""
    slots: List[Dict] = field(default_factory=list)


@dataclass
class CommandBlock:
    command: str
    raw: str
    line_offset: int = 0


@dataclass
class LogFile:
    source_path: str
    device: DeviceMeta
    filename_meta: DeviceMeta
    commands: Dict[str, CommandBlock] = field(default_factory=dict)
    parse_errors: List[str] = field(default_factory=list)


def extract_filename_meta(filepath: str) -> DeviceMeta:
    name = Path(filepath).name
    m = DeviceMeta()
    ip = re.search(r'地址\((\d+\.\d+\.\d+\.\d+)\)', name)
    if ip: m.ip = ip.group(1)
    dev = re.search(r'设备名\(([^)]+)\)', name)
    if dev: m.name = dev.group(1)
    sn = re.search(r'设备SN\(([^)]+)\)', name)
    if sn: m.serial = sn.group(1)
    t = re.search(r'巡检时间\(([^)]+)\)', name)
    if t: m.inspect_time = t.group(1)
    return m


def split_log_file(filepath: str) -> LogFile:
    path = Path(filepath)
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    device = DeviceMeta()
    filename_meta = extract_filename_meta(filepath)
    parse_errors: List[str] = []

    json_match = re.search(r'_deviceInfo_\s*:\s*(\{.*?\})\s*\n', content, re.DOTALL)
    if json_match:
        try:
            info = json.loads(json_match.group(1))
            device.name = info.get('name', '')
            device.model = info.get('model', '')
            device.ip = info.get('ip', '')
            device.hw_version = info.get('hardwareVersion', '')
            device.sw_version = info.get('softwareVersion', '')
            device.serial = info.get('serialNumber', '')
            device.uptime = info.get('upTime', '')
            device.start_time = info.get('startTime', '')
            device.slots = info.get('slots', [])
        except json.JSONDecodeError as e:
            parse_errors.append(f"JSON header parse error: {e}")

    if not device.ip: device.ip = filename_meta.ip
    if not device.name: device.name = filename_meta.name
    if not device.serial: device.serial = filename_meta.serial
    if not device.inspect_time: device.inspect_time = filename_meta.inspect_time

    # split by !---cmd lines
    # each block:
    #   !---cmd <cmd_name>
    #   <device>#<command_execution>
    #   <output>
    #   <device>#
    #   (next !---cmd or EOF)

    cmd_blocks: Dict[str, CommandBlock] = {}
    cmd_starts = [m.start() for m in re.finditer(r'^.*?!---cmd\s+(.*?)$', content, re.MULTILINE)]

    if not cmd_starts:
        parse_errors.append("No !---cmd blocks found in file")
        return LogFile(
            source_path=str(path.resolve()),
            device=device,
            filename_meta=filename_meta,
            parse_errors=parse_errors,
        )

    for idx, start_pos in enumerate(cmd_starts):
        line_start = content.rfind('\n', 0, start_pos) + 1
        end_pos = cmd_starts[idx + 1] if idx + 1 < len(cmd_starts) else len(content)

        header_line = content[start_pos:content.find('\n', start_pos)].strip()
        cmd_match = re.search(r'!---cmd\s+(.*)', header_line)
        if not cmd_match:
            continue
        cmd_name = cmd_match.group(1).strip()

        if '|' in cmd_name:
            continue

        block_text = content[line_start:end_pos]

        lines = block_text.split('\n')
        output_lines = []

        first_data_line = lines[1] if len(lines) > 1 else ''
        hm = re.match(r'^(\S+)#', first_data_line)
        hostname_prefix = hm.group(1) if hm else None

        for line in lines:
            stripped = line.strip()
            if '!---cmd' in stripped:
                continue
            if hostname_prefix and hostname_prefix in stripped:
                if '#' in stripped and not stripped.endswith('#'):
                    continue
                if stripped.rstrip() == hostname_prefix + '#':
                    continue
            output_lines.append(line)

        while output_lines and not output_lines[-1].strip():
            output_lines.pop()
        while output_lines and not output_lines[0].strip():
            output_lines.pop(0)

        raw = '\n'.join(output_lines).strip()
        cmd_blocks[cmd_name] = CommandBlock(
            command=cmd_name,
            raw=raw,
            line_offset=line_start,
        )

    lf = LogFile(
        source_path=str(path.resolve()),
        device=device,
        filename_meta=filename_meta,
        commands=cmd_blocks,
        parse_errors=parse_errors,
    )
    return lf
