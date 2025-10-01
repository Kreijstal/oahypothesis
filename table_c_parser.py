# table_c_parser.py (Enhanced with String Offset Detection)
import struct
import datetime
from dataclasses import dataclass
from typing import List, Optional

# --- Utility Functions ---
def format_int(value): return f"{value} (0x{value:x})"

def is_plausible_string_offset(value):
    """Check if a value looks like a string table offset (typically < 4096)"""
    return 0 < value < 4096

# --- Record Classes ---

@dataclass
class TimestampRecord:
    offset: int; timestamp_val: int; is_primary: bool = True
    def __str__(self):
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
    offset: int; value: int
    def __str__(self):
        return (f"[HYPOTHESIS: Separator Record at {self.offset:#06x} | Size: 16 bytes]\n"
                f"  - Field @ 0x00: Separator -> 0xffffffff\n"
                f"  - Field @ 0x08: Value     -> {format_int(self.value & 0xFFFFFFFF)}")

@dataclass
class TableHeader:
    header_id: int; pointer_list_end_offset: int; internal_pointers: List[int]
    def __str__(self):
        return (f"[HYPOTHESIS: Table Header | Size: {self.pointer_list_end_offset} bytes]\n" +
                f"  - Field @ 0x00: Header ID -> {format_int(self.header_id)}\n" +
                f"  - Field @ 0x08: Pointer List End Offset -> {format_int(self.pointer_list_end_offset)}\n" +
                f"  - Content: Found {len(self.internal_pointers)} 64-bit pointers in this section.")

@dataclass
class PaddingRecord:
    offset: int; size: int; repeated_value: int
    def __str__(self):
        return (f"[HYPOTHESIS: Padding Block at {self.offset:#06x} | Size: {self.size} bytes]\n" +
                f"  - Content: A single integer value {format_int(self.repeated_value)} repeats {self.size // 4} times.")

@dataclass
class NetUpdateRecord:
    offset: int
    size: int
    record_type: int
    net_block_size: int
    related_data_size: int
    unparsed_data: bytes
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        lines = []
        payload = self.unparsed_data
        lines.append(f"[ANALYTICAL PARSE: Netlist Record at {self.offset:#06x} | Aligned Size: {self.size} bytes]")
        lines.append(f"  - Field @ 0x00: Record Type ID -> {format_int(self.record_type)}")
        lines.append(f"  - Field @ 0x04: Block Metadata -> {format_int(self.net_block_size)} (Implies Payload of {len(payload)} bytes)")
        lines.append(f"  - Field @ 0x08: Block Metadata -> {format_int(self.related_data_size)}")

        # Create lookup map for string references
        str_map = {}
        if self.string_references:
            for rec_offset, str_offset, resolved in self.string_references:
                # Map 2-byte aligned offsets to their strings
                str_map[rec_offset] = (str_offset, resolved)

        lines.append("  - Payload Content:")
        num_8byte_records = len(payload) // 8
        remaining_bytes_offset = num_8byte_records * 8
        trailing_bytes = payload[remaining_bytes_offset:]
        lines.append(f"    - Found {num_8byte_records} complete 8-byte descriptor pairs.")
        if trailing_bytes:
            lines.append(f"    - Found {len(trailing_bytes)} trailing/padding bytes.")

        lines.append("\n    --- 8-Byte Descriptor List ---")
        offset = 0
        while offset < remaining_bytes_offset:
            val1, val2 = struct.unpack_from('<II', payload, offset)
            line = f"      Offset 0x{self.offset+12+offset:04x}: (Value: {val1}, Value: {val2})"

            # Check if either value has a string reference
            if offset in str_map:
                _, resolved = str_map[offset]
                line += f" [val1=\"{resolved}\"]"
            if offset + 2 in str_map:
                _, resolved = str_map[offset + 2]
                line += f" [val2=\"{resolved}\"]"

            lines.append(line)
            offset += 8

        if trailing_bytes:
            lines.append("\n    --- Trailing Bytes ---")
            hex_str = ' '.join(f'{b:02x}' for b in trailing_bytes)
            lines.append(f"      Offset 0x{self.offset+12+offset:04x}: {hex_str}")

        return "\n".join(lines)

@dataclass
class PropertyValueRecord:
    offset: int
    size: int
    data: bytes
    property_value_id: int
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        header = f"[IDENTIFIED: Property Value Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
        header += f"  - Property Value ID: {format_int(self.property_value_id)}\n"

        # Create lookup map for string references (byte offset -> string)
        str_map = {}
        if self.string_references:
            for rec_offset, str_offset, resolved in self.string_references:
                str_map[rec_offset] = resolved

        header += "  - Content (summarized as 32-bit integers):\n"
        num_integers = len(self.data) // 4
        if num_integers == 0:
            header += "    (No 32-bit integer data to display)"
            return header.strip()

        # Helper to check if index needs marker
        def needs_marker(idx):
            val = struct.unpack('<I', self.data[idx*4:idx*4+4])[0]
            return (idx*4 == self.property_value_id) or (val == self.property_value_id)

        # Build array of values and markers
        values = [struct.unpack('<I', self.data[i*4:i*4+4])[0] for i in range(num_integers)]
        markers = [needs_marker(i) for i in range(num_integers)]

        # Process array, showing runs but breaking at marker boundaries
        i = 0
        while i < num_integers:
            j = i + 1
            while j < num_integers and values[j] == values[i] and markers[j] == markers[i]:
                j += 1

            count = j - i
            marker_str = " <-- Property Value ID" if markers[i] else ""

            # Check if this 4-byte location has a string reference (check first 2 bytes)
            byte_offset = i * 4
            if byte_offset in str_map:
                marker_str += f" [=\"{str_map[byte_offset]}\"]"

            header += f"    - Index[{i:03d}]: {format_int(values[i])}{marker_str}"
            if count > 1:
                header += f" (repeats {count} times)\n"
            else:
                header += "\n"

            i = j

        return header.strip()

@dataclass
class GenericRecord:
    offset: int
    size: int
    data: bytes
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        header = f"[HYPOTHESIS: Generic Record at {self.offset:#06x} | Size: {self.size} bytes]\n"

        # Create lookup map for string references
        str_map = {}
        if self.string_references:
            for rec_offset, str_offset, resolved in self.string_references:
                str_map[rec_offset] = resolved

        header += "  - Content (summarized as 32-bit integers):\n"
        num_integers = len(self.data) // 4
        if num_integers == 0:
            header += "    (No 32-bit integer data to display)"
            return header.strip()

        last_value = struct.unpack('<I', self.data[0:4])[0]
        repeat_count = 1
        for i in range(1, num_integers):
            current_value = struct.unpack('<I', self.data[i*4:i*4+4])[0]
            if current_value == last_value:
                repeat_count += 1
            else:
                first_idx = i - repeat_count
                byte_offset = first_idx * 4
                suffix = ""
                if byte_offset in str_map:
                    suffix = f" [=\"{str_map[byte_offset]}\"]"

                header += f"    - Index[{first_idx:03d}]: {format_int(last_value)}{suffix}"
                if repeat_count > 1:
                    header += f" (repeats {repeat_count} times)\n"
                else:
                    header += "\n"
                last_value, repeat_count = current_value, 1

        first_idx = num_integers - repeat_count
        byte_offset = first_idx * 4
        suffix = ""
        if byte_offset in str_map:
            suffix = f" [=\"{str_map[byte_offset]}\"]"

        header += f"    - Index[{first_idx:03d}]: {format_int(last_value)}{suffix}"
        if repeat_count > 1:
            header += f" (repeats {repeat_count} times)\n"
        else:
            header += "\n"

        return header.strip()

# --- Main Parser ---

class HypothesisParser:
    # Known offset for R1's property value string reference (from diff analysis)
    R1_RESISTANCE_STRING_OFFSET = 0x797

    def __init__(self, data, string_table_data=None):
        self.data = data
        self.records = []
        self.string_table_data = string_table_data
        self.strings = []

        # Parse string table if provided
        if string_table_data:
            self._parse_string_table()

    def parse(self):
        if not self.data:
            return

        # PASS 1: Parse structure
        try:
            cursor = self._parse_header()
            while cursor < len(self.data):
                initial_cursor = cursor
                if self._try_parse_separator_block(cursor):
                    cursor += 16
                elif self._try_parse_net_update(cursor):
                    cursor += self.records[-1].size
                elif self._try_parse_padding(cursor):
                    cursor += self.records[-1].size
                elif self._try_parse_generic(cursor):
                    cursor += self.records[-1].size
                if cursor == initial_cursor:
                    break
        except Exception:
            pass

        # PASS 2: Find timestamp
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

        # PASS 3: Annotate property values and string references
        self._annotate_property_values()
        self._find_string_references()

    def _try_parse_separator_block(self, c) -> bool:
        if c + 16 > len(self.data):
            return False
        marker = struct.unpack_from('<I', self.data, c)[0]
        if marker == 0xffffffff:
            value_64 = struct.unpack_from('<Q', self.data, c + 8)[0]
            self.records.append(SeparatorRecord(offset=c, value=value_64))
            return True
        return False

    def _parse_header(self) -> int:
        header_id = struct.unpack_from('<I', self.data, 0)[0]
        end_offset = struct.unpack_from('<I', self.data, 8)[0]
        pointers = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
        self.records.append(TableHeader(header_id, end_offset, pointers))
        return end_offset

    def _try_parse_net_update(self, c) -> bool:
        if c + 12 > len(self.data):
            return False
        t, s1, s2 = struct.unpack_from('<III', self.data, c)
        if t == 19 and s1 == s2 and s1 > 0:
            payload_size = s1
            if c + 12 + payload_size > len(self.data):
                return False
            unparsed_bytes = self.data[c + 12 : c + 12 + payload_size]
            full_record_size = 12 + payload_size
            rem = full_record_size % 4
            aligned_size = full_record_size + (4-rem if rem != 0 else 0)
            self.records.append(NetUpdateRecord(c, aligned_size, t, s1, s2, unparsed_bytes, []))
            return True
        return False

    def _try_parse_padding(self, c) -> bool:
        if c + 16 > len(self.data):
            return False
        v, n = struct.unpack_from('<I', self.data, c)[0], 1
        while c + (n + 1) * 4 <= len(self.data) and struct.unpack_from('<I', self.data, c + n * 4)[0] == v:
            n += 1
        if n >= 4:
            self.records.append(PaddingRecord(c, n * 4, v))
            return True
        return False

    def _try_parse_generic(self, c) -> bool:
        end = c + 4
        while end < len(self.data):
            if end + 4 > len(self.data):
                break
            next_id = struct.unpack_from('<I', self.data, end)[0]
            if next_id in [0xffffffff, 19]:
                break
            end += 4
        size = end - c
        if size > 0:
            self.records.append(GenericRecord(c, size, self.data[c:end], []))
            return True
        return False

    def _annotate_property_values(self):
        for i, record in enumerate(self.records):
            if not isinstance(record, GenericRecord):
                continue

            num_ints = len(record.data) // 4
            for j in range(num_ints):
                if j * 4 + 4 > len(record.data):
                    break
                val = struct.unpack_from('<I', record.data, j * 4)[0]

                if 20 < val < 200:
                    has_marker = False
                    for k in range(max(0, j-3), min(num_ints, j+3)):
                        if k * 4 + 4 <= len(record.data):
                            context_val = struct.unpack_from('<I', record.data, k * 4)[0]
                            if context_val in [0xc8000000, 0x00000001, 0x00000002]:
                                has_marker = True
                                break

                    if has_marker:
                        self.records[i] = PropertyValueRecord(
                            offset=record.offset,
                            size=record.size,
                            data=record.data,
                            property_value_id=val,
                            string_references=[]
                        )
                        break

    def _parse_string_table(self):
        """Extract strings from the string table data"""
        if len(self.string_table_data) < 20:
            return

        # Skip 20-byte header
        string_buffer = self.string_table_data[20:]
        current_offset = 0

        while current_offset < len(string_buffer):
            try:
                null_pos = string_buffer.index(b'\0', current_offset)
            except ValueError:
                break

            string_data = string_buffer[current_offset:null_pos]
            if string_data:
                try:
                    decoded = string_data.decode('utf-8')
                    self.strings.append((current_offset, decoded))
                except UnicodeDecodeError:
                    pass

            current_offset = null_pos + 1

    def _lookup_string(self, offset):
        """Look up a string by its offset (accounting for +1 offset pattern)"""
        # Try both the exact offset and offset-1 (since we observed +1 pattern)
        for test_offset in [offset, offset - 1]:
            for str_offset, string in self.strings:
                if str_offset == test_offset:
                    return string
        return None

    def _find_string_references(self):
        """
        Scan all records for 16-bit values that look like string table offsets.
        Only flag values that actually resolve to strings and are meaningful (>100 offset).
        """
        if not self.string_table_data:
            return  # Can't resolve without string table

        for record in self.records:
            if isinstance(record, (GenericRecord, PropertyValueRecord, NetUpdateRecord)):
                string_refs = []
                data = record.data if hasattr(record, 'data') else record.unparsed_data

                # Scan for 16-bit values that could be string offsets
                # Skip very small offsets (0-100) as they cause noise
                for offset in range(0, len(data) - 1, 2):  # Check every 2 bytes
                    val = struct.unpack_from('<H', data, offset)[0]

                    # Only check meaningful offsets
                    if val < 100 or val > 2048:
                        continue

                    # Try to resolve this as a string reference
                    resolved = self._lookup_string(val)
                    if resolved and len(resolved) > 1:  # Ignore single-char strings
                        string_refs.append((offset, val, resolved))

                # Only keep unique string references (avoid duplicates)
                seen = set()
                unique_refs = []
                for offset, val, resolved in string_refs:
                    key = (val, resolved)
                    if key not in seen:
                        seen.add(key)
                        unique_refs.append((offset, val, resolved))

                record.string_references = unique_refs
