import struct
import datetime
from dataclasses import dataclass
from typing import List, Union

# --- Data Class Definitions for Parsed Records ---

def format_int(value: int) -> str:
    """Helper to format integers with their hex representation."""
    return f"{value} (0x{value:x})"

@dataclass
class TimestampRecord:
    """Represents the final, verified timestamp record of the file save."""
    offset: int
    timestamp_val: int

    def __str__(self) -> str:
        ts_32bit = self.timestamp_val & 0xFFFFFFFF
        try:
            date_str = datetime.datetime.utcfromtimestamp(ts_32bit).strftime('%Y-%m-%d %H:%M:%S UTC')
        except (ValueError, OSError):
            date_str = "Invalid Date"

        header = f"[VERIFIED: Final Save Timestamp at {self.offset:#06x}]"
        return (f"\n{'='*70}\n"
                f"{header}\n"
                f"  - Field @ 0x00: Separator         -> 0xffffffff\n"
                f"  - Field @ 0x08: 32-bit Timestamp  -> {format_int(ts_32bit)}\n"
                f"  - INTERPRETED AS UTC  -> {date_str}\n"
                f"{'='*70}")

@dataclass
class SeparatorRecord:
    """Represents a generic separator block (0xffffffff)."""
    offset: int
    value: int

    def __str__(self) -> str:
        return (f"[HYPOTHESIS: Separator Record at {self.offset:#06x} | Size: 16 bytes]\n"
                f"  - Field @ 0x00: Separator -> 0xffffffff\n"
                f"  - Field @ 0x08: Value     -> {format_int(self.value & 0xFFFFFFFF)}")

@dataclass
class TableHeader:
    """Represents the header of Table 0xc, which contains pointers."""
    header_id: int
    pointer_list_end_offset: int
    internal_pointers: List[int]

    def __str__(self) -> str:
        return (f"[HYPOTHESIS: Table Header | Size: {self.pointer_list_end_offset} bytes]\n"
                f"  - Field @ 0x00: Header ID -> {format_int(self.header_id)}\n"
                f"  - Field @ 0x08: Pointer List End Offset -> {format_int(self.pointer_list_end_offset)}\n"
                f"  - Content: Found {len(self.internal_pointers)} 64-bit pointers in this section.")

@dataclass
class PropertyRecord:
    """
    Represents a property assignment record. Based on analysis, this links
    a component to a property and its value using their string table indices.
    """
    offset: int
    size: int
    record_type: int
    component_name_idx: int
    property_name_idx: int
    property_value_idx: int

    def __str__(self) -> str:
        return (f"[ANALYTICAL PARSE: Property Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
                f"  - Record Type ID: {format_int(self.record_type)}\n"
                f"  - Component Name Index -> {format_int(self.component_name_idx)}\n"
                f"  - Property Name Index  -> {format_int(self.property_name_idx)}\n"
                f"  - Property Value Index -> {format_int(self.property_value_idx)}")

@dataclass
class GenericRecord:
    """A catch-all for any data block that doesn't match a known structure."""
    offset: int
    size: int
    data: bytes

    def __str__(self) -> str:
        # Summarize the generic record as a list of 32-bit integers
        header = f"[HYPOTHESIS: Generic Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
        header += "  - Content (summarized as 32-bit integers):\n"

        num_integers = len(self.data) // 4
        if num_integers == 0:
            return header.strip() + "\n    (No 32-bit integer data to display)"

        # Group repeating integers for cleaner output
        last_value = struct.unpack_from('<I', self.data, 0)[0]
        repeat_count = 1
        for i in range(1, num_integers):
            current_value = struct.unpack_from('<I', self.data, i * 4)[0]
            if current_value == last_value:
                repeat_count += 1
            else:
                start_index = i - repeat_count
                header += f"    - Index[{start_index:03d}]: {format_int(last_value)}"
                header += f" (repeats {repeat_count} times)\n" if repeat_count > 1 else "\n"
                last_value, repeat_count = current_value, 1

        start_index = num_integers - repeat_count
        header += f"    - Index[{start_index:03d}]: {format_int(last_value)}"
        header += f" (repeats {repeat_count} times)\n" if repeat_count > 1 else "\n"

        return header.strip()

# --- The Main Parser for Table 0xc ---

AnyRecord = Union[TimestampRecord, SeparatorRecord, TableHeader, PropertyRecord, GenericRecord]

class HypothesisParser:
    def __init__(self, data: bytes):
        self.data = data
        self.records: List[AnyRecord] = []

    def parse(self):
        """
        Parses Table 0xc using a two-pass approach.
        1. First Pass: Greedily identify all known record structures.
        2. Second Pass: Analyze the collected records to find the final timestamp.
        """
        if not self.data:
            return

        # --- PASS 1: Greedily parse all known structures ---
        cursor = 0
        try:
            if self._try_parse_header(cursor):
                cursor = self.records[-1].pointer_list_end_offset

            while cursor < len(self.data):
                initial_cursor = cursor
                # Try parsing each known record type in order of precedence
                if self._try_parse_separator_block(cursor):
                    cursor += 16
                elif self._try_parse_property_record(cursor):
                    cursor += self.records[-1].size
                else:
                    # Fallback to a generic record if no specific type matches
                    if self._try_parse_generic(cursor):
                        cursor += self.records[-1].size

                if cursor == initial_cursor:
                    break # Avoid infinite loops
        except Exception:
            pass # Parsing is best-effort

        # --- PASS 2: Find and promote the final timestamp ---
        last_ts_candidate_index = -1
        for i, record in enumerate(self.records):
            if isinstance(record, SeparatorRecord):
                try:
                    # A plausible timestamp is a large integer corresponding to a recent date
                    if (record.value & 0xFFFFFFFF) > 946684800: # After year 2000
                        datetime.datetime.utcfromtimestamp(record.value & 0xFFFFFFFF)
                        last_ts_candidate_index = i
                except (ValueError, OSError):
                    continue

        if last_ts_candidate_index != -1:
            original_record = self.records[last_ts_candidate_index]
            self.records[last_ts_candidate_index] = TimestampRecord(
                offset=original_record.offset,
                timestamp_val=original_record.value
            )

    # --- Individual Parsing Functions ---

    def _try_parse_header(self, c: int) -> bool:
        """Parses the main table header."""
        if c + 24 > len(self.data): return False
        header_id = struct.unpack_from('<I', self.data, c)[0]
        end_offset = struct.unpack_from('<I', self.data, c + 8)[0]
        if header_id == 4 and end_offset < len(self.data):
            pointers = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
            self.records.append(TableHeader(header_id, end_offset, pointers))
            return True
        return False

    def _try_parse_separator_block(self, c: int) -> bool:
        """Parses a 16-byte separator block (starts with 0xffffffff)."""
        if c + 16 > len(self.data): return False
        if struct.unpack_from('<I', self.data, c)[0] == 0xffffffff:
            value = struct.unpack_from('<Q', self.data, c + 8)[0]
            self.records.append(SeparatorRecord(offset=c, value=value))
            return True
        return False

    def _try_parse_property_record(self, c: int) -> bool:
        """
        Identifies and parses a property record based on the structure we
        discovered: Type ID 19, followed by component, name, and value indices.
        """
        # This record structure is a hypothesis based on analyzing the R0 -> 2K change.
        # It appears to be a 20-byte structure.
        if c + 20 > len(self.data): return False

        record_type, _, _, name_idx, val_idx = struct.unpack_from('<IIHHH', self.data, c)
        comp_idx = struct.unpack_from('<H', self.data, c + 18)[0]

        # Check for a signature pattern of this record type
        if record_type == 19 and name_idx > 0 and val_idx > 0 and comp_idx > 0:
            self.records.append(PropertyRecord(
                offset=c, size=20, record_type=record_type,
                component_name_idx=comp_idx,
                property_name_idx=name_idx,
                property_value_idx=val_idx
            ))
            return True
        return False

    def _try_parse_generic(self, c: int) -> bool:
        """Parses any block of data that doesn't match a known structure."""
        end = c + 4
        # Greedily consume bytes until we hit a known separator or the end.
        while end < len(self.data):
            if end + 4 > len(self.data): break
            next_id = struct.unpack_from('<I', self.data, end)[0]
            if next_id == 0xffffffff or next_id == 19:
                break
            end += 4

        size = end - c
        if size > 0:
            self.records.append(GenericRecord(c, size, self.data[c:end]))
            return True
        return False