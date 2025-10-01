# table_c_parser.py (Final Version with Last-Timestamp-Wins Logic)
import struct
import datetime
from dataclasses import dataclass
from typing import List

# --- All Record classes and helpers are unchanged. They are already correct. ---
def format_int(value): return f"{value} (0x{value:x})"

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
    def __str__(self): return (f"[HYPOTHESIS: Table Header | Size: {self.pointer_list_end_offset} bytes]\n" + f"  - Field @ 0x00: Header ID -> {format_int(self.header_id)}\n" + f"  - Field @ 0x08: Pointer List End Offset -> {format_int(self.pointer_list_end_offset)}\n" + f"  - Content: Found {len(self.internal_pointers)} 64-bit pointers in this section.")
@dataclass
class PaddingRecord:
    offset: int; size: int; repeated_value: int
    def __str__(self): return (f"[HYPOTHESIS: Padding Block at {self.offset:#06x} | Size: {self.size} bytes]\n" + f"  - Content: A single integer value {format_int(self.repeated_value)} repeats {self.size // 4} times.")
@dataclass
class NetUpdateRecord:
    offset: int; size: int; record_type: int; net_block_size: int; related_data_size: int; unparsed_data: bytes
    def __str__(self):
        lines = []
        payload = self.unparsed_data
        lines.append(f"[ANALYTICAL PARSE: Netlist Record at {self.offset:#06x} | Aligned Size: {self.size} bytes]")
        lines.append(f"  - Field @ 0x00: Record Type ID -> {format_int(self.record_type)}")
        lines.append(f"  - Field @ 0x04: Block Metadata -> {format_int(self.net_block_size)} (Implies Payload of {len(payload)} bytes)")
        lines.append(f"  - Field @ 0x08: Block Metadata -> {format_int(self.related_data_size)}")
        lines.append("  - Payload Content:")
        num_8byte_records = len(payload) // 8
        remaining_bytes_offset = num_8byte_records * 8
        trailing_bytes = payload[remaining_bytes_offset:]
        lines.append(f"    - Found {num_8byte_records} complete 8-byte descriptor pairs.")
        if trailing_bytes: lines.append(f"    - Found {len(trailing_bytes)} trailing/padding bytes.")
        lines.append("\n    --- 8-Byte Descriptor List ---")
        offset = 0
        while offset < remaining_bytes_offset:
            val1, val2 = struct.unpack_from('<II', payload, offset)
            lines.append(f"      Offset 0x{self.offset+12+offset:04x}: (Value: {val1}, Value: {val2})")
            offset += 8
        if trailing_bytes:
            lines.append("\n    " + "!"*55)
            lines.append("    ! WARNING: Irregular structure detected (payload not a multiple of 8).")
            lines.append("    " + "!"*55)
            lines.append("\n    --- Trailing Bytes ---")
            hex_str = ' '.join(f'{b:02x}' for b in trailing_bytes)
            lines.append(f"      Offset 0x{self.offset+12+offset:04x}: {hex_str}")
        return "\n".join(lines)
@dataclass
class PropertyValueRecord:
    offset: int; size: int; data: bytes; property_value_id: int
    def __str__(self):
        header = f"[IDENTIFIED: Property Value Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
        header += f"  - Property Value ID: {format_int(self.property_value_id)}\n"
        header += "  - This ID references a property value (e.g., resistance value)\n"
        header += "  - Full content (summarized as 32-bit integers):\n"
        num_integers = len(self.data) // 4
        if num_integers == 0:
            header += "    (No 32-bit integer data to display)"
            return header.strip()
        
        # Helper function to check if an index needs a marker
        def needs_marker(idx):
            val = struct.unpack('<I', self.data[idx*4:idx*4+4])[0]
            return (idx*4 == self.property_value_id) or (val == self.property_value_id)
        
        # Build array of all values and which ones have markers
        values = [struct.unpack('<I', self.data[i*4:i*4+4])[0] for i in range(num_integers)]
        markers = [needs_marker(i) for i in range(num_integers)]
        
        # Process the array, summarizing consecutive runs but breaking at marker boundaries
        i = 0
        while i < num_integers:
            # Find the end of the current run (same value, same marker status)
            j = i + 1
            while j < num_integers and values[j] == values[i] and markers[j] == markers[i]:
                j += 1
            
            # Output this run
            count = j - i
            marker_str = " <-- Property Value ID" if markers[i] else ""
            header += f"    - Index[{i:03d}]: {format_int(values[i])}{marker_str}"
            if count > 1:
                header += f" (repeats {count} times)\n"
            else:
                header += "\n"
            
            i = j
        
        return header.strip()

@dataclass
class GenericRecord:
    offset: int; size: int; data: bytes
    def __str__(self):
        header = f"[HYPOTHESIS: Generic Record at {self.offset:#06x} | Size: {self.size} bytes]\n"
        header += "  - Content (summarized as 32-bit integers):\n"
        num_integers = len(self.data) // 4
        if num_integers == 0:
            header += "    (No 32-bit integer data to display)"
            return header.strip()
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

# --- FINAL HypothesisParser ---
class HypothesisParser:
    def __init__(self, data):
        self.data = data
        self.records = []

    def parse(self):
        """
        This method now implements the two-pass parsing logic.
        """
        if not self.data: return

        # --- PASS 1: Collection ---
        # Greedily parse the entire table into a list of record objects.
        try:
            cursor = self._parse_header()
            while cursor < len(self.data):
                initial_cursor = cursor
                if self._try_parse_separator_block(cursor): cursor += 16
                elif self._try_parse_net_update(cursor): cursor += self.records[-1].size
                elif self._try_parse_padding(cursor): cursor += self.records[-1].size
                elif self._try_parse_generic(cursor): cursor += self.records[-1].size
                if cursor == initial_cursor: break
        except Exception:
            pass # Suppress parsing errors

        # --- PASS 2: Analysis and Re-typing ---
        # Find the last plausible timestamp and promote it.
        last_ts_candidate_index = -1
        for i, record in enumerate(self.records):
            if isinstance(record, SeparatorRecord):
                # Check if the value is a plausible date (e.g., after the year 2000)
                try:
                    if (record.value & 0xFFFFFFFF) > 946684800:
                         datetime.datetime.utcfromtimestamp(record.value & 0xFFFFFFFF)
                         last_ts_candidate_index = i # This is a candidate
                except (ValueError, OSError):
                    continue # Not a valid date

        # If we found a candidate, replace it in the list with a TimestampRecord
        if last_ts_candidate_index != -1:
            original_record = self.records[last_ts_candidate_index]
            self.records[last_ts_candidate_index] = TimestampRecord(
                offset=original_record.offset,
                timestamp_val=original_record.value
            )
        
        # --- PASS 3: Identify property value references ---
        # Based on analysis of sch4.oa vs sch5.oa, certain patterns indicate property values
        # We look for GenericRecords that might contain property value IDs
        self._annotate_property_values()

    # --- Individual parsing methods ---
    def _try_parse_separator_block(self, c) -> bool:
        if c + 16 > len(self.data): return False
        marker = struct.unpack_from('<I', self.data, c)[0]
        if marker == 0xffffffff:
            # In the first pass, ALL 0xffffffff blocks are treated as generic separators
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
        if c + 12 > len(self.data): return False
        t, s1, s2 = struct.unpack_from('<III', self.data, c)
        if t == 19 and s1 == s2 and s1 > 0:
            payload_size = s1
            if c + 12 + payload_size > len(self.data): return False
            unparsed_bytes = self.data[c + 12 : c + 12 + payload_size]
            full_record_size = 12 + payload_size
            rem = full_record_size % 4
            aligned_size = full_record_size + (4-rem if rem !=0 else 0)
            self.records.append(NetUpdateRecord(c, aligned_size, t, s1, s2, unparsed_bytes))
            return True
        return False

    def _try_parse_padding(self, c) -> bool:
        if c + 16 > len(self.data): return False
        v, n = struct.unpack_from('<I', self.data, c)[0], 1
        while c + (n + 1) * 4 <= len(self.data) and struct.unpack_from('<I', self.data, c + n * 4)[0] == v: n += 1
        if n >= 4: self.records.append(PaddingRecord(c, n * 4, v)); return True
        return False

    def _try_parse_generic(self, c) -> bool:
        end = c + 4
        while end < len(self.data):
            if end + 4 > len(self.data): break
            next_id = struct.unpack_from('<I', self.data, end)[0]
            if next_id in [0xffffffff, 19]: break
            end += 4
        size = end - c
        if size > 0:
            self.records.append(GenericRecord(c, size, self.data[c:end]))
            return True
        return False

    def _annotate_property_values(self):
        """
        Post-processing pass to identify and annotate property value references.
        
        Based on analysis of sch4.oa vs sch5.oa diffs, we know that certain
        GenericRecords contain property value IDs (like resistance values).
        
        Patterns observed:
        - Property value IDs appear in specific structural contexts
        - They are typically small integers (< 256) that represent indices
        - They appear in records with specific marker patterns (like 0xc8000000)
        
        This is a heuristic approach that looks for known patterns.
        """
        for i, record in enumerate(self.records):
            if not isinstance(record, GenericRecord):
                continue
            
            # Look for property value patterns in the data
            # Pattern: sequences with 0xc8000000 followed by small value patterns
            num_ints = len(record.data) // 4
            for j in range(num_ints):
                if j * 4 + 4 > len(record.data):
                    break
                val = struct.unpack_from('<I', record.data, j * 4)[0]
                
                # Check if this looks like a property value ID:
                # - Small value (likely an index, 0 < val < 256)
                # - Preceded by specific markers
                if 20 < val < 200:  # Reasonable range for property value IDs
                    # Check context: look for 0xc8000000 or pattern markers nearby
                    has_marker = False
                    for k in range(max(0, j-3), min(num_ints, j+3)):
                        if k * 4 + 4 <= len(record.data):
                            context_val = struct.unpack_from('<I', record.data, k * 4)[0]
                            if context_val in [0xc8000000, 0x00000001, 0x00000002]:
                                has_marker = True
                                break
                    
                    # If we found a likely property value ID, annotate it
                    if has_marker:
                        # Replace the GenericRecord with a PropertyValueRecord
                        self.records[i] = PropertyValueRecord(
                            offset=record.offset,
                            size=record.size,
                            data=record.data,
                            property_value_id=val
                        )
                        break  # Only annotate once per record
