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
class ComponentRecord:
    """
    Represents a component's data block in the netlist. This contains a list
    of indices pointing to property values in the string table.
    """
    offset: int
    size: int
    component_index: int
    property_value_indices: List[int]

    def __str__(self) -> str:
        lines = [f"[ANALYTICAL PARSE: Component Record at {self.offset:#06x} | Size: {self.size} bytes]"]
        lines.append(f"  - Component Index: {format_int(self.component_index)} (e.g., 'R0')")
        lines.append(f"  - Property Value Indices:")
        for i, val_idx in enumerate(self.property_value_indices):
            lines.append(f"    - Prop[{i}]: Index -> {format_int(val_idx)}")
        return "\n".join(lines)

@dataclass
class GenericRecord:
    """A catch-all for any data block that doesn't match a known structure."""
    offset: int
    size: int
    data: bytes

    def __str__(self) -> str:
        header = f"[HYPOTHESIS: Generic Record at {self.offset:#06x} | Size: {self.size} bytes]"
        return header

# --- The Main Parser for Table 0xc ---

AnyRecord = Union[TimestampRecord, SeparatorRecord, TableHeader, ComponentRecord, GenericRecord]

class HypothesisParser:
    def __init__(self, data: bytes):
        self.data = data
        self.records: List[AnyRecord] = []

    def parse(self):
        if not self.data: return

        # Pass 1: Greedily parse known structures
        cursor = 0
        try:
            if self._try_parse_header(cursor):
                cursor = self.records[-1].pointer_list_end_offset

            while cursor < len(self.data):
                initial_cursor = cursor
                if self._try_parse_separator_block(cursor):
                    cursor += 16
                elif self._try_parse_component_record(cursor):
                    cursor += self.records[-1].size
                else:
                    if self._try_parse_generic(cursor):
                        cursor += self.records[-1].size

                if cursor == initial_cursor: break
        except Exception:
            pass

        # Pass 2: Identify and promote the final timestamp
        last_ts_candidate_index = -1
        for i, record in enumerate(self.records):
            if isinstance(record, SeparatorRecord):
                try:
                    if (record.value & 0xFFFFFFFF) > 946684800:
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

    def _try_parse_header(self, c: int) -> bool:
        if c + 24 > len(self.data): return False
        header_id, end_offset = struct.unpack_from('<II', self.data, c)[0], struct.unpack_from('<I', self.data, c + 8)[0]
        if header_id == 4 and end_offset < len(self.data):
            pointers = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
            self.records.append(TableHeader(header_id, end_offset, pointers))
            return True
        return False

    def _try_parse_separator_block(self, c: int) -> bool:
        if c + 16 > len(self.data): return False
        if struct.unpack_from('<I', self.data, c)[0] == 0xffffffff:
            value = struct.unpack_from('<Q', self.data, c + 8)[0]
            self.records.append(SeparatorRecord(offset=c, value=value))
            return True
        return False

    def _try_parse_component_record(self, c: int) -> bool:
        # A component record starts with its own string index as a 2-byte int.
        if c + 4 > len(self.data): return False
        comp_idx = struct.unpack_from('<H', self.data, c)[0]

        # Heuristic: component indices are small numbers. This helps avoid false positives.
        if 1 <= comp_idx < 100:
            # The next 2 bytes seem to be a size field.
            payload_size = struct.unpack_from('<H', self.data, c + 2)[0]

            # The full record size must be aligned to 4 bytes.
            full_size = 4 + payload_size
            aligned_size = full_size + (4 - full_size % 4) if full_size % 4 != 0 else full_size

            if c + aligned_size <= len(self.data):
                payload_data = self.data[c + 4 : c + 4 + payload_size]

                # The payload is a list of 2-byte value indices.
                value_indices = [struct.unpack_from('<H', payload_data, i)[0] for i in range(0, len(payload_data), 2)]

                self.records.append(ComponentRecord(
                    offset=c, size=aligned_size, component_index=comp_idx,
                    property_value_indices=value_indices
                ))
                return True
        return False

    def _try_parse_generic(self, c: int) -> bool:
        end = c + 4
        while end < len(self.data):
            if end + 4 > len(self.data): break
            next_id = struct.unpack_from('<I', self.data, end)[0]
            comp_idx_cand = struct.unpack_from('<H', self.data, end)[0]
            if next_id == 0xffffffff or (1 <= comp_idx_cand < 100):
                break
            end += 4

        size = end - c
        if size > 0:
            self.records.append(GenericRecord(c, size, self.data[c:end]))
            return True
        return False