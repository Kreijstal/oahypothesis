# table_c_parser.py - Refactored to use BinaryCurator
import struct
import datetime
from dataclasses import dataclass
from typing import List, Optional
from oaparser.binary_curator import BinaryCurator, Region, NestedUnclaimedData

# --- Utility Functions ---
def format_int(value): return f"{value} (0x{value:x})"

# --- Record Classes ---
@dataclass
class TimestampRecord:
    offset: int; timestamp_val: int
    def __str__(self):
        ts_32bit = self.timestamp_val & 0xFFFFFFFF
        try: date_str = datetime.datetime.utcfromtimestamp(ts_32bit).strftime('%Y-%m-%d %H:%M:%S UTC')
        except (ValueError, OSError): date_str = "Invalid Date"
        return f"Timestamp: {format_int(ts_32bit)} = {date_str}"

@dataclass
class SeparatorRecord:
    offset: int; value: int
    def __str__(self): return f"Separator: 0xffffffff, Value: {format_int(self.value & 0xFFFFFFFF)}"

@dataclass
class TableHeader:
    header_id: int; pointer_list_end_offset: int; raw_all_fields: List[int]
    def __str__(self):
        return (f"Header ID: {format_int(self.header_id)}\n"
                f"Header Size: {self.pointer_list_end_offset} bytes\n"
                f"Total Fields: {len(self.raw_all_fields)}")

@dataclass
class PaddingRecord:
    offset: int; size: int; repeated_value: int
    def __str__(self): return f"Padding: {format_int(self.repeated_value)} x{self.size // 4}"

@dataclass
class GenericRecord:
    offset: int; size: int
    def __str__(self): return f"Generic Record: {self.size} bytes"

@dataclass
class TransientStateRecord:
    offset: int
    payload: bytes

    def get_state_description(self) -> str:
        # Unpack as two signed integers
        val1, val2 = struct.unpack('<ii', self.payload)
        if val1 == 0 and val2 == -1:
            return f"State 1 (Resistance Set): values=({val1}, {val2})"
        elif val1 == 1 and val2 == 2:
            return f"State 2 (Component Type Change): values=({val1}, {val2})"
        else:
            return f"Unknown State: payload={self.payload.hex(' ')}"

    def __str__(self):
        return f"Transient State Record @ 0x{self.offset:x}\n  - {self.get_state_description()}"

@dataclass
class ComponentPropertyRecord:
    offset: int; data: bytes
    EXPECTED_CONFIG = bytes.fromhex(
        "06000000050000000100000000000000"
        "02000000000000000300000000000000"
        "04000000000000000003000000000000"
        "a400000000000000a800000000000000"
        "ac00000000000000b000000000000000"
        "b400000000000000"
    )
    def __str__(self): return f"Component Property Record (132 bytes)"

# --- Main Parser ---
class HypothesisParser:
    def __init__(self, data, string_table_data=None):
        self.data = data
        self.curator = BinaryCurator(self.data)

    def parse(self) -> List[Region]:
        if not self.data: return self.curator.get_regions()
        header_end = self._parse_header()
        timestamp_offset, _ = self._find_timestamp()
        scan_end = timestamp_offset if timestamp_offset is not None else len(self.data)
        
        self._scan_and_parse(header_end, scan_end)
        
        if timestamp_offset:
            self.curator.seek(timestamp_offset)
            sep_info = self._check_separator(timestamp_offset)
            if sep_info:
                self.curator.claim("Timestamp", 16, lambda d, ts=timestamp_offset, tv=sep_info[1]: TimestampRecord(ts, tv))
                remaining_start = timestamp_offset + 16
                if remaining_start < len(self.data):
                    self._claim_generic(remaining_start, len(self.data) - remaining_start)
        
        return self.curator.get_regions()

    def _scan_and_parse(self, start: int, end: int):
        cursor = start
        while cursor < end:
            # Attempt to claim known record types one by one
            claimed_size = (
                self._try_claim_transient_state_record(cursor) or
                self._try_claim_component_property(cursor) or
                self._try_claim_net_update(cursor) or
                self._try_claim_separator(cursor) or
                self._try_claim_padding(cursor)
            )
            
            if claimed_size:
                cursor += claimed_size
            else:
                # If no known record is found, claim one byte as generic and advance
                self._claim_generic(cursor, 1)
                cursor += 1

    def _try_claim_transient_state_record(self, offset: int) -> int:
        """
        Detects and claims the 24-byte transient state record.
        - Header: 08 00 00 00 03 00 00 00
        - Payload: 8 bytes (defines the state)
        - Footer: 00 00 00 c8 02 00 00 00
        """
        RECORD_SIZE = 24
        if offset + RECORD_SIZE > len(self.data):
            return 0

        # Check for the constant header and footer patterns
        header = self.data[offset : offset + 8]
        footer = self.data[offset + 16 : offset + 24]

        if header == b'\x08\x00\x00\x00\x03\x00\x00\x00' and footer == b'\x00\x00\x00\xc8\x02\x00\x00\x00':
            payload = self.data[offset + 8 : offset + 16]
            self.curator.claim(
                "TransientStateRecord",
                RECORD_SIZE,
                lambda d, o=offset, p=payload: TransientStateRecord(o, p)
            )
            return RECORD_SIZE

        return 0

    def _try_claim_component_property(self, offset):
        s_size, cfg_off = 132, 8
        if offset + s_size > len(self.data): return 0
        cfg = self.data[offset + cfg_off : offset + cfg_off + 88]
        if cfg == ComponentPropertyRecord.EXPECTED_CONFIG:
            self.curator.claim("ComponentPropertyRecord", s_size, lambda d, o=offset: ComponentPropertyRecord(o, self.data[o:o+s_size]))
            return s_size
        return 0

    def _claim_generic(self, offset, size):
        if size > 0: self.curator.claim("Generic", size, lambda d, o=offset, s=size: GenericRecord(o, s))

    def _parse_header(self) -> int:
        if len(self.data) < 16: return 0
        try:
            header_id, _, end_offset, _ = struct.unpack_from('<IIQI', self.data, 0)
            if end_offset > len(self.data) or end_offset < 8: return 0
            all_fields = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
            self.curator.claim("Table Header", end_offset, lambda d: TableHeader(header_id, end_offset, all_fields))
            return end_offset
        except struct.error:
            return 0

    def _find_timestamp(self):
        offset = len(self.data) - 20
        if offset > 0:
            sep_info = self._check_separator(offset)
            if sep_info:
                pos, val = sep_info
                if (val & 0xFFFFFFFF) > 946684800:
                    try:
                        datetime.datetime.utcfromtimestamp(val & 0xFFFFFFFF)
                        return pos, val
                    except (ValueError, OSError): pass
        return None, None

    def _check_separator(self, cursor):
        if cursor + 16 <= len(self.data) and struct.unpack_from('<I', self.data, cursor)[0] == 0xffffffff:
            return cursor, struct.unpack_from('<Q', self.data, cursor + 8)[0]
        return None
    def _try_claim_separator(self, cursor) -> int:
        sep_info = self._check_separator(cursor)
        if sep_info:
            self.curator.claim("Separator", 16, lambda d, p=sep_info[0], v=sep_info[1]: SeparatorRecord(p, v))
            return 16
        return 0
    def _try_claim_net_update(self, cursor) -> int:
        if cursor + 12 > len(self.data): return 0
        try:
            t, s1, s2 = struct.unpack_from('<III', self.data, cursor)
            if t != 19 or s1 != s2 or s1 <= 0 or cursor + 12 + s1 > len(self.data): return 0
            size = 12 + s1 + (4 - (12 + s1) % 4) % 4
            self.curator.claim("NetUpdate", size, lambda d: f"NetUpdate Record ({size} bytes)")
            return size
        except struct.error:
            return 0
    def _try_claim_padding(self, cursor) -> int:
        if cursor + 16 > len(self.data): return 0
        try:
            v, n = struct.unpack_from('<I', self.data, cursor)[0], 1
            while cursor + (n + 1) * 4 <= len(self.data) and struct.unpack_from('<I', self.data, cursor + n * 4)[0] == v: n += 1
            if n >= 4:
                self.curator.claim("Padding", n * 4, lambda d, o=cursor, s=n*4, val=v: PaddingRecord(o, s, val))
                return n * 4
        except struct.error:
            return 0
        return 0
    def _parse_string_table(self): pass
    def _find_string_refs_in_data(self, data): return []
    def _lookup_string(self, offset): return None