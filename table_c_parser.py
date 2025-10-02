# table_c_parser.py - Refactored to use BinaryCurator
import struct
import datetime
from dataclasses import dataclass
from typing import List, Optional
from oaparser.binary_curator import BinaryCurator, Region

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
    header_id: int; pointer_list_end_offset: int; internal_pointers: List[int]
    def __str__(self):
        return f"Header ID: {format_int(self.header_id)}, Pointers: {len(self.internal_pointers)}"

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
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        parts = [f"NetUpdate Type:{format_int(self.record_type)}"]
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            parts.append(f"Strings:{','.join(strs)}")
        return " ".join(parts)

@dataclass
class PropertyValueRecord:
    offset: int
    size: int
    data: bytes
    property_value_id: int
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        parts = [f"PropertyValue ID:{format_int(self.property_value_id)}"]
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            parts.append(f"Strings:{','.join(strs)}")
        return " ".join(parts)

@dataclass
class GenericRecord:
    offset: int
    size: int
    data: bytes
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        parts = [f"Generic {len(self.data)}bytes"]
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            parts.append(f"Strings:{','.join(strs)}")
        return " ".join(parts)

# --- Main Parser ---

class HypothesisParser:
    # Known offset for R1's property value string reference (from diff analysis)
    R1_RESISTANCE_STRING_OFFSET = 0x797

    def __init__(self, data, string_table_data=None):
        self.data = data
        self.string_table_data = string_table_data
        self.strings = []
        self.curator = BinaryCurator(self.data)

        # Parse string table if provided
        if string_table_data:
            self._parse_string_table()

    def parse(self) -> List[Region]:
        """Parse table 0xc using BinaryCurator and return regions"""
        if not self.data:
            return self.curator.get_regions()

        # PASS 1: Parse header
        try:
            header_end = self._parse_header_with_curator()
            
            # PASS 2: Find all separators first to identify timestamp
            separator_positions = []
            cursor = header_end
            while cursor < len(self.data):
                sep_info = self._check_separator(cursor)
                if sep_info:
                    separator_positions.append(sep_info)
                    cursor += 16
                    continue
                    
                # Skip other structures for now
                if cursor + 12 <= len(self.data):
                    t = struct.unpack_from('<I', self.data, cursor)[0]
                    if t == 19:
                        s1, s2 = struct.unpack_from('<II', self.data, cursor + 4)
                        if s1 == s2 and s1 > 0:
                            payload_size = s1
                            full_size = 12 + payload_size
                            rem = full_size % 4
                            aligned_size = full_size + (4-rem if rem != 0 else 0)
                            cursor += aligned_size
                            continue
                
                # Check for padding
                if cursor + 16 <= len(self.data):
                    v = struct.unpack_from('<I', self.data, cursor)[0]
                    n = 1
                    while cursor + (n + 1) * 4 <= len(self.data):
                        next_val = struct.unpack_from('<I', self.data, cursor + n * 4)[0]
                        if next_val != v:
                            break
                        n += 1
                    if n >= 4:
                        cursor += n * 4
                        continue
                
                # Generic - advance by 4
                cursor += 4
                if cursor >= len(self.data):
                    break
            
            # Find the last valid timestamp
            timestamp_pos = None
            timestamp_val = None
            for pos, val in reversed(separator_positions):
                ts_32bit = val & 0xFFFFFFFF
                if ts_32bit > 946684800:
                    try:
                        datetime.datetime.utcfromtimestamp(ts_32bit)
                        timestamp_pos = pos
                        timestamp_val = val
                        break
                    except (ValueError, OSError):
                        continue
            
            # PASS 3: Claim all structures with timestamp marked
            cursor = header_end
            while cursor < len(self.data):
                initial_cursor = cursor
                
                # Try separator
                sep_info = self._check_separator(cursor)
                if sep_info:
                    cursor_pos, value_64 = sep_info
                    self.curator.seek(cursor)
                    if cursor == timestamp_pos:
                        self.curator.claim(
                            "Timestamp",
                            16,
                            lambda d, v=timestamp_val: TimestampRecord(cursor, v)
                        )
                    else:
                        self.curator.claim(
                            "Separator",
                            16,
                            lambda d, p=cursor_pos, v=value_64: SeparatorRecord(p, v)
                        )
                    cursor += 16
                    continue
                    
                net_size = self._try_claim_net_update(cursor)
                if net_size > 0:
                    cursor += net_size
                    continue
                    
                pad_size = self._try_claim_padding(cursor)
                if pad_size > 0:
                    cursor += pad_size
                    continue
                    
                # Try to identify and claim property values
                # If we can't identify it, skip forward to continue parsing
                # but DON'T claim it - leave as unclaimed data
                gen_size = self._try_claim_property_value(cursor)
                if gen_size > 0:
                    cursor += gen_size
                    continue
                
                # If we couldn't identify anything specific, skip a small amount
                # to avoid infinite loop, but leave data unclaimed
                if cursor == initial_cursor:
                    # Skip 4 bytes and continue looking for structures
                    cursor += 4
                    if cursor >= len(self.data):
                        break
                    
        except Exception:
            pass

        return self.curator.get_regions()

    def _parse_header_with_curator(self) -> int:
        """Parse header using BinaryCurator"""
        if len(self.data) < 16:
            return 0
            
        header_id = struct.unpack_from('<I', self.data, 0)[0]
        end_offset = struct.unpack_from('<I', self.data, 8)[0]
        
        if end_offset > len(self.data) or end_offset < 8:
            return 0
            
        pointers = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
        
        self.curator.claim(
            "Table Header",
            end_offset,
            lambda d: TableHeader(header_id, end_offset, pointers)
        )
        
        return end_offset

    def _check_separator(self, cursor):
        """Check if there's a separator at this position, return (cursor, value) or None"""
        if cursor + 16 > len(self.data):
            return None
            
        marker = struct.unpack_from('<I', self.data, cursor)[0]
        if marker != 0xffffffff:
            return None
            
        value_64 = struct.unpack_from('<Q', self.data, cursor + 8)[0]
        return (cursor, value_64)

    def _try_claim_separator(self, cursor) -> int:
        """Try to claim a separator block at cursor position"""
        sep_info = self._check_separator(cursor)
        if not sep_info:
            return 0
            
        cursor_pos, value_64 = sep_info
        
        self.curator.seek(cursor)
        self.curator.claim(
            "Separator",
            16,
            lambda d: SeparatorRecord(cursor_pos, value_64)
        )
        
        return 16

    def _try_claim_net_update(self, cursor) -> int:
        """Try to claim a net update record at cursor position"""
        if cursor + 12 > len(self.data):
            return 0
            
        t, s1, s2 = struct.unpack_from('<III', self.data, cursor)
        
        if t != 19 or s1 != s2 or s1 <= 0:
            return 0
            
        payload_size = s1
        if cursor + 12 + payload_size > len(self.data):
            return 0
            
        unparsed_bytes = self.data[cursor + 12 : cursor + 12 + payload_size]
        full_record_size = 12 + payload_size
        rem = full_record_size % 4
        aligned_size = full_record_size + (4-rem if rem != 0 else 0)
        
        # Find string references in this record
        string_refs = self._find_string_refs_in_data(unparsed_bytes)
        
        self.curator.seek(cursor)
        self.curator.claim(
            "NetUpdate",
            aligned_size,
            lambda d: NetUpdateRecord(cursor, aligned_size, t, s1, s2, unparsed_bytes, string_refs)
        )
        
        return aligned_size

    def _try_claim_padding(self, cursor) -> int:
        """Try to claim a padding block at cursor position"""
        if cursor + 16 > len(self.data):
            return 0
            
        v = struct.unpack_from('<I', self.data, cursor)[0]
        n = 1
        
        while cursor + (n + 1) * 4 <= len(self.data):
            next_val = struct.unpack_from('<I', self.data, cursor + n * 4)[0]
            if next_val != v:
                break
            n += 1
        
        if n < 4:
            return 0
            
        size = n * 4
        self.curator.seek(cursor)
        self.curator.claim(
            "Padding",
            size,
            lambda d: PaddingRecord(cursor, size, v)
        )
        
        return size

    def _try_claim_property_value(self, cursor) -> int:
        """Try to identify and claim a property value record - ONLY if we can positively identify it"""
        # Look ahead to find a reasonable boundary (separator or net update marker)
        end = cursor + 4
        while end < len(self.data):
            if end + 4 > len(self.data):
                break
            next_id = struct.unpack_from('<I', self.data, end)[0]
            if next_id in [0xffffffff, 19]:
                break
            end += 4
        
        size = end - cursor
        if size <= 0:
            return 0
            
        record_data = self.data[cursor:end]
        
        # Check if this is a property value record
        property_value_id = self._check_property_value(record_data)
        
        # ONLY claim if we can positively identify it as a property value
        # Otherwise, leave it unclaimed for full hex dump visibility
        if property_value_id is not None:
            string_refs = self._find_string_refs_in_data(record_data)
            self.curator.seek(cursor)
            self.curator.claim(
                "PropertyValue",
                size,
                lambda d, p=cursor, s=size, rd=record_data, pid=property_value_id, sr=string_refs: 
                    PropertyValueRecord(p, s, rd, pid, sr)
            )
            return size
        
        # Don't claim - leave as unclaimed for hex dump
        return 0

    def _check_property_value(self, data: bytes) -> Optional[int]:
        """Check if data looks like a property value record"""
        num_ints = len(data) // 4
        for j in range(num_ints):
            if j * 4 + 4 > len(data):
                break
            val = struct.unpack_from('<I', data, j * 4)[0]
            
            if 20 < val < 200:
                # Check for markers in context
                has_marker = False
                for k in range(max(0, j-3), min(num_ints, j+3)):
                    if k * 4 + 4 <= len(data):
                        context_val = struct.unpack_from('<I', data, k * 4)[0]
                        if context_val in [0xc8000000, 0x00000001, 0x00000002]:
                            has_marker = True
                            break
                
                if has_marker:
                    return val
        
        return None

    def _find_string_refs_in_data(self, data: bytes) -> List[tuple]:
        """Find string references in a data block"""
        if not self.string_table_data:
            return []
            
        string_refs = []
        
        # Scan for 16-bit values that could be string offsets
        for offset in range(0, len(data) - 1, 2):
            val = struct.unpack_from('<H', data, offset)[0]
            
            if val < 100 or val > 2048:
                continue
                
            resolved = self._lookup_string(val)
            if resolved and len(resolved) > 1:
                string_refs.append((offset, val, resolved))
        
        # Deduplicate
        seen = set()
        unique_refs = []
        for offset, val, resolved in string_refs:
            key = (val, resolved)
            if key not in seen:
                seen.add(key)
                unique_refs.append((offset, val, resolved))
        
        return unique_refs

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
