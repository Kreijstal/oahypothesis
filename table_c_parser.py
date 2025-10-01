# table_c_parser.py (Corrected and Enhanced Version)
import struct
import datetime
from dataclasses import dataclass
from typing import List, Union

# --- Helper and Dataclasses ---
def format_int(value): return f"{value} (0x{value:x})"

@dataclass
class TableHeader:
    # ... (same as before) ...
    header_id: int; pointer_list_end_offset: int; internal_pointers: List[int]
    def __str__(self): return (f"[HYPOTHESIS: Table Header | Size: {self.pointer_list_end_offset} bytes]\n" + f"  - Field @ 0x00: Header ID -> {format_int(self.header_id)}\n" + f"  - Field @ 0x08: Pointer List End Offset -> {format_int(self.pointer_list_end_offset)}\n" + f"  - Content: Found {len(self.internal_pointers)} 64-bit pointers in this section.")

@dataclass
class TimestampRecord:
    offset: int
    timestamp_val: int

    @property
    def decoded_time_utc(self):
        try:
            # The timestamp is the lower 32 bits of the 64-bit value
            return datetime.datetime.utcfromtimestamp(self.timestamp_val & 0xFFFFFFFF).strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
            return "Invalid Date"

    def __str__(self):
        return (f"[HYPOTHESIS: Timestamp Record at {self.offset:#06x} | Size: 16 bytes]\n"
                f"  - Field @ 0x00: Separator -> 0xffffffff\n"
                f"  - Field @ 0x08: Timestamp Value -> {format_int(self.timestamp_val & 0xFFFFFFFF)}\n"
                f"  - INTERPRETED -> {self.decoded_time_utc}")

# ... (Other record classes like Padding, Netlist, Generic are the same) ...
@dataclass
class PaddingRecord:
    offset: int; size: int; repeated_value: int
    def __str__(self): return (f"[HYPOTHESIS: Padding Block at {self.offset:#06x} | Size: {self.size} bytes]\n" + f"  - Content: A single integer value {format_int(self.repeated_value)} repeats {self.size // 4} times.")
@dataclass
class NetUpdateRecord:
    offset: int; size: int; record_type: int; net_block_size: int; related_data_size: int
    def __str__(self): return (f"[HYPOTHESIS: Netlist Record at {self.offset:#06x} | Size: {self.size} bytes]\n" + f"  - Field @ 0x00: Record Type ID -> {format_int(self.record_type)}\n" + f"  - Field @ 0x04: Net Block Size -> {format_int(self.net_block_size)}\n" + f"  - Field @ 0x08: Related Data Size -> {format_int(self.related_data_size)}\n" + f"  - ... (remaining {self.size - 12} bytes of data are unparsed)")
@dataclass
class GenericRecord:
    offset: int; size: int; data: bytes
    def __str__(self):
        header = f"[HYPOTHESIS: Generic Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
        header += "  - Content (summarized view):\n"
        num_integers = len(self.data) // 4
        if num_integers == 0: return header.strip()
        last_value = struct.unpack('<I', self.data[0:4])[0]
        repeat_count = 1
        for i in range(1, num_integers):
            current_value = struct.unpack('<I', self.data[i*4:i*4+4])[0]
            if current_value == last_value: repeat_count += 1
            else:
                first_idx = i - repeat_count
                header += f"    - Index[{first_idx:03d}]: {format_int(last_value)}"
                if repeat_count > 1: header += f" (repeats {repeat_count} times)\n"
                else: header += "\n"
                last_value, repeat_count = current_value, 1
        first_idx = num_integers - repeat_count
        header += f"    - Index[{first_idx:03d}]: {format_int(last_value)}"
        if repeat_count > 1: header += f" (repeats {repeat_count} times)\n"
        else: header += "\n"
        return header.strip()

class HypothesisParser:
    def __init__(self, data): self.data = data; self.records = []
    def parse(self):
        if not self.data: return
        try:
            cursor = self._parse_header()
            while cursor < len(self.data):
                initial_cursor = cursor
                # Give the specific timestamp parser priority
                if self._try_parse_timestamp_record(cursor): cursor += 16
                elif self._try_parse_net_update(cursor): cursor += self.records[-1].size
                elif self._try_parse_padding(cursor): cursor += self.records[-1].size
                elif self._try_parse_generic(cursor): cursor += self.records[-1].size
                if cursor == initial_cursor: break
        except Exception: pass

    def _parse_header(self) -> int:
        header_id = struct.unpack_from('<I', self.data, 0)[0]
        end_offset = struct.unpack_from('<I', self.data, 8)[0]
        # Hypothesis: The header is an array of 64-bit pointers
        pointers = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
        self.records.append(TableHeader(header_id, end_offset, pointers))
        return end_offset

    def _try_parse_timestamp_record(self, c) -> bool:
        if c + 16 > len(self.data): return False
        marker = struct.unpack_from('<I', self.data, c)[0]
        if marker == 0xffffffff:
            # Read the next 8 bytes as a potential 64-bit timestamp field
            ts_val_64 = struct.unpack_from('<Q', self.data, c + 8)[0]
            ts_val_32 = ts_val_64 & 0xFFFFFFFF # We know the value is in the lower 32 bits

            # Heuristic check for plausibility
            try:
                datetime.datetime.utcfromtimestamp(ts_val_32)
                # If it doesn't raise an error, it's a valid date.
                self.records.append(TimestampRecord(c, ts_val_64))
                return True
            except (ValueError, OSError): # OSError for dates before 1970 on some systems
                return False
        return False

    # ... (The other _try_parse methods remain the same, but are now less likely to be called for timestamp records) ...
    def _try_parse_padding(self, c) -> bool:
        if c + 16 > len(self.data): return False
        v, n = struct.unpack_from('<I', self.data, c)[0], 1
        while c + (n + 1) * 4 <= len(self.data) and struct.unpack_from('<I', self.data, c + n * 4)[0] == v: n += 1
        if n >= 4: self.records.append(PaddingRecord(c, n * 4, v)); return True
        return False
    def _try_parse_net_update(self, c) -> bool:
        if c + 12 > len(self.data): return False
        t, s1, s2 = struct.unpack_from('<III', self.data, c)
        if t == 19 and s1 == s2 and s1 > 0: self.records.append(NetUpdateRecord(c, 124, t, s1, s2)); return True
        return False
    def _try_parse_generic(self, c) -> bool:
        end = c + 4
        while end < len(self.data):
            if struct.unpack_from('<I', self.data, end)[0] in [0xffffffff, 19]: break
            end += 4
        if (size := end - c) > 0: self.records.append(GenericRecord(c, size, self.data[c:end])); return True
        return False
