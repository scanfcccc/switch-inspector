import re

SHORT_MAP = {
    'Gi': 'GigabitEthernet',
    'Te': 'TenGigabitEthernet',
    'Twe': 'TwentyFiveGigabitEthernet',
    'TF': 'TFGigabitEthernet',
    'Fo': 'FortyGigabitEthernet',
    'Hu': 'HundredGigabitEthernet',
    'Vl': 'VLAN',
    'Lo': 'Loopback',
    'Po': 'AggregatePort',
    'Ag': 'AggregatePort',
    'Eth': 'Ethernet',
}

FULL_PREFIXES = [
    'GigabitEthernet', 'TenGigabitEthernet',
    'TwentyFiveGigabitEthernet', 'FortyGigabitEthernet',
    'HundredGigabitEthernet', 'Ethernet',
    'TFGigabitEthernet',
    'VLAN', 'Loopback', 'AggregatePort',
    'FastEthernet',
]

def normalize_iface(name: str) -> str:
    name = name.strip()
    if not name:
        return name

    for prefix in FULL_PREFIXES:
        if name.startswith(prefix):
            parts = name[len(prefix):].strip().split()
            if parts:
                slot_port = parts[0]
                if '/' in slot_port:
                    return f"{prefix} {slot_port}"
            return name

    m = re.match(r'([A-Za-z]+)(\d+[\/\d]*)', name)
    if m:
        prefix = m.group(1)
        rest = m.group(2)
        full = SHORT_MAP.get(prefix, prefix)
        if '/' in rest:
            return f"{full} {rest}"
        return f"{full} {rest}"

    return name

def normalize_port_id(name: str) -> str:
    name = name.strip()
    # If it looks like a MAC address, return as-is
    if re.match(r'^([0-9a-fA-F]{2}\.){2}[0-9a-fA-F]{2}\.[0-9a-fA-F]{2}\.[0-9a-fA-F]{4}$', name):
        return name
    m = re.match(r'([A-Za-z]+)(\d+/\d+(?:/\d+)?)', name)
    if m:
        short = m.group(1)
        rest = m.group(2)
        s2 = {'Te': 'TenGigabitEthernet', 'Gi': 'GigabitEthernet',
              'Twe': 'TwentyFiveGigabitEthernet', 'TF': 'TFGigabitEthernet',
              'Fo': 'FortyGigabitEthernet', 'Hu': 'HundredGigabitEthernet',
              'Po': 'AggregatePort', 'Eth': 'Ethernet'}.get(short, short)
        return f"{s2} {rest}"
    return name
