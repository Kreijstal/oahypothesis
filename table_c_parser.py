# table_c_parser.py - Refactored to use BinaryCurator
import struct
import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from oaparser.binary_curator import BinaryCurator, Region, NestedUnclaimedData
import os

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
        return f"Timestamp: {format_int(ts_32bit)} = {date_str}"

@dataclass
class SeparatorRecord:
    offset: int; value: int
    def __str__(self):
        return f"Separator: 0xffffffff, Value: {format_int(self.value & 0xFFFFFFFF)}"

@dataclass
class TableHeader:
    header_id: int
    pointer_list_end_offset: int
    first_record_offset: int
    unknown_offsets_1_30: List[int]
    boundary_offsets_31_33: List[int]
    config_values: List[int]
    raw_all_fields: List[int]
    
    @property
    def offsets(self) -> List[int]:
        result = [self.first_record_offset]
        result.extend(self.unknown_offsets_1_30)
        result.extend(self.boundary_offsets_31_33)
        return result
    
    def __str__(self):
        lines = [
            f"Header ID: {format_int(self.header_id)}",
            f"Header Size: {self.pointer_list_end_offset} bytes",
            f"Total Fields: {len(self.raw_all_fields)}",
            "",
            "--- Header Fields (in original order) ---"
        ]
        if not self.raw_all_fields:
            lines.append("  (No fields to display)")
            return "\n".join(lines)
        i = 0
        while i < len(self.raw_all_fields):
            val = self.raw_all_fields[i]
            count = 1
            j = i + 1
            while j < len(self.raw_all_fields) and self.raw_all_fields[j] == val:
                count += 1
                j += 1
            if count > 3:
                lines.append(f"  [Fields {i:03d}-{j-1:03d}]: 0x{val:x} (repeats {count} times)")
                i = j
            else:
                for k in range(i, j):
                    lines.append(f"  [Field {k:03d}]: 0x{val:x}")
                i = j
        return "\n".join(lines)

@dataclass
class PaddingRecord:
    offset: int; size: int; repeated_value: int
    def __str__(self):
        return f"Padding: {format_int(self.repeated_value)} x{self.size // 4}"

@dataclass
class NetUpdateRecord:
    offset: int
    size: int
    record_type: int
    net_block_size: int
    related_data_size: int
    unparsed_data: bytes
    string_references: List[tuple]

    def __str__(self):
        header_parts = [f"NetUpdate Type:{format_int(self.record_type)}"]
        header_parts.append(f"BlockSize:{format_int(self.net_block_size)}")
        header_parts.append(f"RelatedSize:{format_int(self.related_data_size)}")
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            header_parts.append(f"Strings:{','.join(strs)}")
        lines = [" ".join(header_parts)]
        if self.unparsed_data:
            lines.append("Content (summarized as 32-bit integers):")
            data = self.unparsed_data
            padding = len(data) % 4
            if padding != 0:
                data += b'\x00' * (4 - padding)
            int_array = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]
            i = 0
            while i < len(int_array):
                num = int_array[i]
                j = i + 1
                while j < len(int_array) and int_array[j] == num:
                    j += 1
                repeat_count = j - i
                string_annotation = ""
                byte_offset_start = i * 4
                byte_offset_end = byte_offset_start + 4
                for str_offset, _, resolved_str in self.string_references:
                    if byte_offset_start <= str_offset < byte_offset_end:
                        string_annotation = f' [="{resolved_str}"]'
                        break
                line = f"- Index[{i:03d}]: {num} (0x{num:x}){string_annotation}"
                if repeat_count > 1:
                    line += f" (repeats {repeat_count} times)"
                lines.append(line)
                i = j
        return "\n".join(lines)

@dataclass
class PropertyValueRecord:
    offset: int
    size: int
    data: bytes
    property_value_id: int
    string_references: List[tuple]
    record_type: Optional[int] = None
    marker: Optional[int] = None
    unclaimed_payload: Optional[NestedUnclaimedData] = None

    def __str__(self):
        lines = []
        parts = [f"PropertyValue ID:{format_int(self.property_value_id)}"]
        if self.record_type is not None: parts.append(f"Type:{format_int(self.record_type)}")
        if self.marker is not None: parts.append(f"Marker:{format_int(self.marker)}")
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            parts.append(f"Strings:{','.join(strs)}")
        lines.append(" ".join(parts))
        if self.unclaimed_payload:
            lines.append("")
            lines.append(str(self.unclaimed_payload))
        return "\n".join(lines)

@dataclass
class GenericRecord:
    offset: int
    size: int
    data: bytes
    string_references: List[tuple]

    def __str__(self):
        header_parts = []
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references]
            header_parts.append(f"Strings: {','.join(strs)}")
        lines = [" ".join(header_parts)]
        lines.append("Content (summarized as 32-bit integers):")
        data = self.data
        padding = len(data) % 4
        if padding != 0: data += b'\x00' * (4 - padding)
        if not data: return " ".join(header_parts)
        int_array = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]
        summary_lines = []
        i = 0
        while i < len(int_array):
            num = int_array[i]
            j = i + 1
            while j < len(int_array) and int_array[j] == num:
                j += 1
            repeat_count = j - i
            string_annotation = ""
            byte_offset_start = i * 4
            byte_offset_end = byte_offset_start + 4
            for str_offset, _, resolved_str in self.string_references:
                if byte_offset_start <= str_offset < byte_offset_end:
                    string_annotation = f' [="{resolved_str}"]'
                    break
            line = f"- Index[{i:03d}]: {num} (0x{num:x}){string_annotation}"
            if repeat_count > 1:
                line += f" (repeats {repeat_count} times)"
            summary_lines.append(line)
            i = j
        lines.extend(summary_lines)
        return "\n".join(lines)

def _generate_diff(expected: bytes, actual: bytes) -> List[str]:
    diff_lines = []
    for i in range(0, len(expected), 16):
        exp_chunk = expected[i:i+16]
        act_chunk = actual[i:i+16]
        if exp_chunk != act_chunk:
            diff_lines.extend([
                f"    {i:04x}:",
                f"      - Expected: {' '.join(f'{b:02x}' for b in exp_chunk)}",
                f"      - Actual:   {' '.join(f'{b:02x}' for b in act_chunk)}"
            ])
    return diff_lines

@dataclass
class UnknownStruct60Byte:
    offset: int
    data: bytes
    padding: bytes
    config_pattern: bytes
    payload: bytes
    trailing_separator: bytes
    OBSERVED_PATTERN = bytes.fromhex("0800000003000000")
    OBSERVED_SEPARATOR = bytes.fromhex("000000c802000000e8001a03")
    def __str__(self):
        lines = [f"Unknown 60-byte Structure (HYPOTHETICAL - appears only in sch5-8)"]
        lines.append(f"  Total Size: {len(self.data)} bytes")
        lines.append(f"  - Padding: {len(self.padding)} bytes")
        if self.config_pattern == self.OBSERVED_PATTERN:
            lines.append(f"  - Pattern: 8 bytes (matches observed 08 00 00 00 03 00 00 00)")
        else:
            lines.append(f"  - Pattern: 8 bytes (DIFFERENT from observed)")
            lines.extend(_generate_diff(self.OBSERVED_PATTERN, self.config_pattern))
        payload_ints_str = "empty"
        if self.payload:
            payload_ints = [f"0x{v:x}" for v in struct.unpack(f'<{len(self.payload)//4}I', self.payload)]
            payload_ints_str = f"{{{', '.join(payload_ints)}}}"
        lines.append(f"  - Payload: {len(self.payload)} bytes, Values: {payload_ints_str}")
        if self.trailing_separator == self.OBSERVED_SEPARATOR:
            lines.append(f"  - Trailing: 12 bytes (ends with separator-like pattern)")
        else:
            lines.append(f"  - Trailing: 12 bytes (DIFFERENT)")
            lines.extend(_generate_diff(self.OBSERVED_SEPARATOR, self.trailing_separator))
        return "\n".join(lines)

@dataclass
class ComponentPropertyRecord:
    """
    Parses the 132-byte structure that appears to define a component property.
    This structure has a static header and a dynamic value ID at the end.
    """
    offset: int
    data: bytes  # The raw 132 bytes

    # Parsed fields (initialized in __post_init__)
    structure_id: int = field(init=False)
    config_and_pointers: bytes = field(init=False)
    padding: bytes = field(init=False)
    value_id: int = field(init=False)

    # Assertion results (initialized in __post_init__)
    config_matches: bool = field(init=False)
    padding_matches: bool = field(init=False)

    # Class-level constants
    RECORD_SIZE = 132
    SIGNATURE = b'\xa4\x00\x00\x00\x00\x00\x00\x00'
    
    # Expected patterns
    EXPECTED_CONFIG = bytes.fromhex(
        "06000000050000000100000000000000"
        "02000000000000000300000000000000"
        "04000000000000000003000000000000"
        "a400000000000000a800000000000000"
        "ac00000000000000b000000000000000"
        "b400000000000000"
    )
    EXPECTED_PADDING = bytes.fromhex(
        "04000000000000000400000000000000"
        "04000000000000000400000000000000"
    )
    
    def __post_init__(self):
        """Parse the raw data after the object is created."""
        if len(self.data) != 132:
            raise ValueError(f"ComponentPropertyRecord expects 132 bytes, got {len(self.data)}")
        
        self.structure_id = struct.unpack_from('<Q', self.data, 0)[0]
        self.config_and_pointers = self.data[8:96]
        self.padding = self.data[96:128]
        self.value_id = struct.unpack_from('<I', self.data, 128)[0]
        self.config_matches = (self.config_and_pointers == self.EXPECTED_CONFIG)
        self.padding_matches = (self.padding == self.EXPECTED_PADDING)

    def __str__(self):
        lines = [
            "Component Property Record (132 bytes)",
            f"  - Structure Type ID: 0x{self.structure_id:016x}",
            f"  - Value ID: {self.value_id} (0x{self.value_id:x})",
        ]

        if self.config_matches:
            lines.append("  - Config/Pointers (88 bytes): OK (matches known pattern)")
        else:
            lines.append("  - Config/Pointers (88 bytes): MISMATCH")
            lines.extend(_generate_diff(self.EXPECTED_CONFIG, self.config_and_pointers))

        if self.padding_matches:
            lines.append("  - Padding (32 bytes): OK (matches known pattern)")
        else:
            lines.append("  - Padding (32 bytes): MISMATCH")
            lines.extend(_generate_diff(self.EXPECTED_PADDING, self.padding))

        return "\n".join(lines)

class HypothesisParser:
    R1_RESISTANCE_STRING_OFFSET = 0x797
    def __init__(self, data, string_table_data=None, filepath=None):
        self.data = data
        self.string_table_data = string_table_data
        self.filepath = filepath
        self.strings = []
        self.curator = BinaryCurator(self.data)
        if string_table_data:
            self._parse_string_table()

    def parse(self) -> List[Region]:
        if not self.data:
            return self.curator.get_regions()
        try:
            header_end = self._parse_header_with_curator()
            header_region = self.curator.regions[0] if self.curator.regions else None
            if not header_region or not isinstance(header_region.parsed_value, TableHeader):
                return self._parse_legacy_fallback(header_end)
            header = header_region.parsed_value
            timestamp_offset, timestamp_val = None, None
            TIMESTAMP_OFFSET_FROM_END = 20
            if len(self.data) >= TIMESTAMP_OFFSET_FROM_END + 16:
                candidate_timestamp_offset = len(self.data) - TIMESTAMP_OFFSET_FROM_END
                sep_info = self._check_separator(candidate_timestamp_offset)
                if sep_info:
                    pos, val = sep_info
                    if (val & 0xFFFFFFFF) > 946684800:
                        try:
                            datetime.datetime.utcfromtimestamp(val & 0xFFFFFFFF)
                            timestamp_offset, timestamp_val = pos, val
                        except (ValueError, OSError): pass
            return self._parse_pointer_driven(header, header_end, timestamp_offset, timestamp_val)
        except ValueError:
            # Re-raise ValueError (including overlap detection errors) to caller
            raise

    def _parse_header_with_curator(self) -> int:
        if len(self.data) < 16: return 0
        header_id = struct.unpack_from('<I', self.data, 0)[0]
        end_offset = struct.unpack_from('<I', self.data, 8)[0]
        if end_offset > len(self.data) or end_offset < 8: return 0
        all_fields = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
        self.curator.claim("Table Header", end_offset, lambda d: TableHeader(header_id=header_id, pointer_list_end_offset=end_offset, first_record_offset=all_fields[0] if all_fields else 0, unknown_offsets_1_30=all_fields[1:31] if len(all_fields) > 31 else [], boundary_offsets_31_33=all_fields[31:34] if len(all_fields) > 33 else [], config_values=all_fields[34:] if len(all_fields) > 34 else [], raw_all_fields=all_fields))
        return end_offset

    def _parse_pointer_driven(self, header: TableHeader, header_end: int, timestamp_offset: Optional[int], timestamp_val: Optional[int]) -> List[Region]:
        candidate_offsets = sorted(
            {o for o in header.offsets if header_end <= o < len(self.data)}
        )
        if not candidate_offsets: return self._parse_legacy_fallback(header_end, timestamp_offset, timestamp_val)
        valid_offsets = [candidate_offsets[0]]
        for offset in candidate_offsets[1:]:
            if offset - valid_offsets[-1] >= 32: valid_offsets.append(offset)
        for i in range(len(valid_offsets)):
            start_offset = valid_offsets[i]
            end_offset = valid_offsets[i + 1] if i + 1 < len(valid_offsets) else len(self.data)
            
            # If there's a timestamp, adjust the segment boundaries
            if timestamp_offset:
                # If this segment would cross the timestamp, end it at the timestamp
                if start_offset < timestamp_offset < end_offset:
                    end_offset = timestamp_offset
                # Skip segments that start at or after where the timestamp starts
                # because the timestamp and everything after will be handled separately
                elif start_offset >= timestamp_offset:
                    continue
            
            if end_offset - start_offset > 0: 
                self._claim_record_segment(start_offset, end_offset - start_offset)
        
        if timestamp_offset:
            last_before_ts = next((off for off in reversed(valid_offsets) if off < timestamp_offset), header_end)
            if timestamp_offset > last_before_ts:
                self.curator.seek(timestamp_offset)
                self.curator.claim("Timestamp", 16, lambda d, v=timestamp_val: TimestampRecord(timestamp_offset, v))
                remaining_start = timestamp_offset + 16
                if remaining_start < len(self.data):
                    if len(self.data) - remaining_start > 0: self._claim_generic_or_property(remaining_start, len(self.data) - remaining_start)
        return self.curator.get_regions()
    
    def _claim_record_segment(self, offset: int, size: int):
        if size <= 0: return
        self.curator.seek(offset)
        if size >= 16:
            sep_info = self._check_separator(offset)
            if sep_info:
                self.curator.claim("Separator", 16, lambda d, p=sep_info[0], v=sep_info[1]: SeparatorRecord(p, v))
                if size > 16: self._claim_record_segment(offset + 16, size - 16)
                return
        if size >= 12:
            t = struct.unpack_from('<I', self.data, offset)[0]
            if t == 19 and len(self.data[offset:]) >= 12:
                s1, s2 = struct.unpack_from('<II', self.data, offset + 4)
                if s1 == s2 and s1 > 0 and (12 + s1) <= size:
                    net_size = self._try_claim_net_update(offset)
                    if net_size > 0:
                        if size > net_size: self._claim_record_segment(offset + net_size, size - net_size)
                        return
        if size >= 16:
            pad_size = self._try_claim_padding(offset)
            if pad_size > 0 and pad_size <= size:
                if size > pad_size: self._claim_record_segment(offset + pad_size, size - pad_size)
                return
        self._claim_generic_or_property(offset, size)

    def _claim_generic_or_property(self, offset: int, size: int):
        """
        Scans a block of data for ComponentPropertyRecord structures.
        Any data surrounding these structures is claimed as generic or property value.
        """
        if size <= 0:
            return

        magic_number = ComponentPropertyRecord.SIGNATURE
        struct_size = ComponentPropertyRecord.RECORD_SIZE

        block_data = self.data[offset : offset + size]
        cursor = 0

        while cursor < size:
            # Find the next occurrence of our magic number from the current cursor
            found_pos = block_data.find(magic_number, cursor)

            if found_pos != -1 and (size - found_pos) >= struct_size:
                # Found a potential record.

                # 1. Claim data *before* the found record as generic/property
                pre_chunk_size = found_pos - cursor
                if pre_chunk_size > 0:
                    pre_chunk_offset = offset + cursor
                    self._claim_as_generic_or_property_value(pre_chunk_offset, pre_chunk_size)

                # 2. Claim the ComponentPropertyRecord itself
                struct_offset = offset + found_pos
                self.curator.seek(struct_offset)
                struct_data = self.data[struct_offset : struct_offset + struct_size]
                self.curator.claim(
                    "ComponentPropertyRecord",
                    struct_size,
                    lambda d, p=struct_offset, rd=struct_data: ComponentPropertyRecord(
                        offset=p,
                        data=rd
                    )
                )

                # 3. Update cursor to after the claimed struct
                cursor = found_pos + struct_size
            else:
                # No more occurrences found, claim the rest of the block
                remaining_size = size - cursor
                if remaining_size > 0:
                    remaining_offset = offset + cursor
                    self._claim_as_generic_or_property_value(remaining_offset, remaining_size)
                # Exit the loop
                break

    def _check_and_claim_unknown_struct(self, offset: int, size: int) -> bool:
        """
        Checks if a data block matches the unknown 60-byte structure pattern.
        WARNING: This structure only appears in sch5-8, disappears after.
        Returns True if claimed, False otherwise.
        """
        # Observed pattern (UNSTABLE - disappears in sch9+)
        PATTERN_SIG = UnknownStruct60Byte.OBSERVED_PATTERN
        SEPARATOR_SIG = UnknownStruct60Byte.OBSERVED_SEPARATOR
        MIN_SIZE = len(PATTERN_SIG) + len(SEPARATOR_SIG)  # Must be at least 20 bytes

        if size < MIN_SIZE:
            return False

        record_data = self.data[offset : offset + size]
        
        # The pattern is not at a fixed position due to variable padding.
        # We find the pattern block, then check if it ends with the separator.
        pattern_pos = record_data.find(PATTERN_SIG)
        
        valid_record_starts = []
        scan_cursor = 0
        while scan_cursor < size:
            found_pos = block_data.find(magic_number, scan_cursor)
            if found_pos == -1: break
            struct_start_in_block = found_pos - magic_number_offset_in_struct
            if struct_start_in_block >= 0 and (struct_start_in_block + struct_size) <= size:
                valid_record_starts.append(offset + struct_start_in_block)
            scan_cursor = found_pos + 1
        
        last_claimed_end = offset
        # Remove duplicates while preserving order
        seen = set()
        ordered_unique_record_starts = []
        for record_start in valid_record_starts:
            if record_start not in seen:
                seen.add(record_start)
                ordered_unique_record_starts.append(record_start)
        for record_start in ordered_unique_record_starts:
            if record_start < last_claimed_end: continue
            pre_chunk_size = record_start - last_claimed_end
            if pre_chunk_size > 0: self._claim_as_generic_or_property_value(last_claimed_end, pre_chunk_size)
            
            self.curator.seek(record_start)
            struct_data = self.data[record_start : record_start + struct_size]
            self.curator.claim("ComponentPropertyRecord", struct_size,
                lambda d, p=record_start, rd=struct_data: ComponentPropertyRecord(
                    offset=p, data=rd,
                    structure_id=struct.unpack_from('<Q', rd, 0)[0],
                    value_id=struct.unpack_from('<I', rd, 128)[0],
                    config_matches=(rd[8:96] == ComponentPropertyRecord.EXPECTED_CONFIG),
                    full_data_view=self.data,  # Pass the full table view
                    filepath=self.filepath))
            last_claimed_end = record_start + struct_size
        
        remaining_size = (offset + size) - last_claimed_end
        if remaining_size > 0:
            self._claim_as_generic_or_property_value(last_claimed_end, remaining_size)

    def _claim_as_generic_or_property_value(self, offset, size):
        if size <= 0: return
        if self._check_and_claim_unknown_struct(offset, size): return
        record_data = self.data[offset : offset + size]
        property_value_info = self._check_property_value(record_data)
        self.curator.seek(offset)
        string_refs = self._find_string_refs_in_data(record_data)
        if property_value_info is not None:
            self.curator.claim("PropertyValue", size, lambda d, p=offset, s=size, rd=record_data, info=property_value_info, sr=string_refs: PropertyValueRecord(offset=p, size=s, data=rd, property_value_id=info['property_value_id'], string_references=sr, record_type=info['record_type'], marker=info['marker'], unclaimed_payload=info['unclaimed_payload']))
        else:
            self.curator.claim("Generic", size, lambda d, p=offset, s=size, rd=record_data, sr=string_refs: GenericRecord(p, s, rd, sr))

    def _check_and_claim_unknown_struct(self, offset: int, size: int) -> bool:
        PATTERN_SIG, SEPARATOR_SIG = UnknownStruct60Byte.OBSERVED_PATTERN, UnknownStruct60Byte.OBSERVED_SEPARATOR
        if size < len(PATTERN_SIG) + len(SEPARATOR_SIG): return False
        record_data = self.data[offset : offset + size]
        pattern_pos = record_data.find(PATTERN_SIG)
        if pattern_pos != -1 and record_data.endswith(SEPARATOR_SIG):
            payload_start = pattern_pos + len(PATTERN_SIG)
            payload_end = size - len(SEPARATOR_SIG)
            if payload_start <= payload_end:
                padding, pattern, payload, separator = record_data[:pattern_pos], record_data[pattern_pos:payload_start], record_data[payload_start:payload_end], record_data[payload_end:]
                self.curator.claim("UnknownStruct60Byte", size, lambda d: UnknownStruct60Byte(offset=offset, data=record_data, padding=padding, config_pattern=pattern, payload=payload, trailing_separator=separator))
                return True
        return False

    def _check_property_value(self, data: bytes) -> Optional[dict]:
        if len(data) < 32: return None
        record_type, marker, _, _, _, _, _, val_at_index_7 = struct.unpack_from('<IIIIIIII', data, 0)
        if record_type == 19 and marker == 0xc8000000 and 20 < val_at_index_7 < 200:
            unclaimed_bytes = data[32:] if len(data) > 32 else b''
            return {
                'property_value_id': val_at_index_7,
                'record_type': record_type,
                'marker': marker,
                'unclaimed_payload': (
                    NestedUnclaimedData(
                        label="UNCLAIMED PAYLOAD",
                        data=unclaimed_bytes,
                        description="Unknown data within PropertyValueRecord (after first 32 bytes)",
                    )
                    if unclaimed_bytes
                    else None
                ),
            }
        return None

    def _find_string_refs_in_data(self, data: bytes) -> List[tuple]:
        if not self.string_table_data: return []
        refs = []
        for offset in range(0, len(data) - 1, 2):
            val = struct.unpack_from('<H', data, offset)[0]
            if 100 < val < 2048:
                resolved = self._lookup_string(val)
                if resolved and len(resolved) > 1: refs.append((offset, val, resolved))
        return list({(v, r): (o, v, r) for o, v, r in refs}.values())

    def _parse_string_table(self):
        if len(self.string_table_data) < 20: return
        pos = 20
        while pos < len(self.string_table_data):
            end = self.string_table_data.find(b'\x00', pos)
            if end == -1: break
            try: self.strings.append((pos - 20, self.string_table_data[pos:end].decode('utf-8')))
            except UnicodeDecodeError: pass
            pos = end + 1

    def _lookup_string(self, offset):
        return next(
            (
                string
                for str_offset, string in self.strings
                if str_offset in [offset, offset - 1]
            ),
            None,
        )

    def _parse_legacy_fallback(self, header_end: int, timestamp_offset: Optional[int] = None, timestamp_val: Optional[int] = None) -> List[Region]:
        return self.curator.get_regions() # Simplified for brevity

    def _check_separator(self, cursor):
        if cursor + 16 > len(self.data): return None
        marker = struct.unpack_from('<I', self.data, cursor)[0]
        if marker != 0xffffffff: return None
        return (cursor, struct.unpack_from('<Q', self.data, cursor + 8)[0])

    def _try_claim_net_update(self, cursor) -> int: return 0
    def _try_claim_padding(self, cursor) -> int: return 0