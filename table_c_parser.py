# table_c_parser.py - Refactored to use BinaryCurator
import struct
import datetime
from dataclasses import dataclass
from typing import List, Optional
from oaparser.binary_curator import BinaryCurator, Region, NestedUnclaimedData

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
    """
    Table 0xc header structure (716 bytes).
    
    The header is a struct with 89 uint64 fields (4 + 89*8 = 716 bytes):
    - Fields 0-33: Location-dependent offsets (shift when data is inserted)
    - Fields 34+: Static configuration values
    
    Some fields have been identified:
    - Field [0]: first_record_offset (always 0x2cc in observed files)
    - Fields [31-33]: Record boundary offsets (shift with data changes)
    """
    header_id: int
    pointer_list_end_offset: int
    
    # Known named fields
    first_record_offset: int  # Field [0], always 0x2cc
    
    # Unknown fields (stored as lists for now)
    unknown_offsets_1_30: List[int]  # Fields [1-30]
    boundary_offsets_31_33: List[int]  # Fields [31-33], verified to be offsets
    
    config_values: List[int]  # Fields 34+: Static configuration values
    
    # For binary curator completeness, store all raw values
    raw_all_fields: List[int]
    
    @property
    def offsets(self) -> List[int]:
        """Get all offset fields (0-33) for backward compatibility."""
        result = [self.first_record_offset]
        result.extend(self.unknown_offsets_1_30)
        result.extend(self.boundary_offsets_31_33)
        return result
    
    def __str__(self):
        """
        Prints all header fields sequentially, preserving their original order.
        Summarizes long runs of identical values to maintain readability.
        """
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

            # Check for repeated values
            count = 1
            j = i + 1
            while j < len(self.raw_all_fields) and self.raw_all_fields[j] == val:
                count += 1
                j += 1

            if count > 3:  # Summarize if 4 or more repeats
                lines.append(f"  [Fields {i:03d}-{j-1:03d}]: 0x{val:x} (repeats {count} times)")
                i = j  # Move index past the repeated block
            else:
                # Print individual fields if not part of a long run
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
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        """Display all NetUpdate data according to Binary Curator principle."""
        # Header line with type and block sizes
        header_parts = [f"NetUpdate Type:{format_int(self.record_type)}"]
        header_parts.append(f"BlockSize:{format_int(self.net_block_size)}")
        header_parts.append(f"RelatedSize:{format_int(self.related_data_size)}")

        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            header_parts.append(f"Strings:{','.join(strs)}")

        lines = [" ".join(header_parts)]

        # Display the unparsed_data content as 32-bit integers
        if self.unparsed_data:
            lines.append("Content (summarized as 32-bit integers):")

            # Pad data to 4-byte alignment
            data = self.unparsed_data
            padding = len(data) % 4
            if padding != 0:
                data += b'\x00' * (4 - padding)

            int_array = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]

            # Display integers with run-length encoding for repeated values
            i = 0
            while i < len(int_array):
                num = int_array[i]

                # Find how many times this number repeats consecutively
                j = i + 1
                while j < len(int_array) and int_array[j] == num:
                    j += 1
                repeat_count = j - i

                # Check if this integer's byte offset corresponds to a string reference
                string_annotation = ""
                byte_offset_start = i * 4
                byte_offset_end = byte_offset_start + 4
                for str_offset, _, resolved_str in self.string_references:
                    if byte_offset_start <= str_offset < byte_offset_end:
                        string_annotation = f' [="{resolved_str}"]'
                        break

                # Format the output line
                line = f"- Index[{i:03d}]: {num} (0x{num:x}){string_annotation}"
                if repeat_count > 1:
                    line += f" (repeats {repeat_count} times)"
                lines.append(line)

                i = j  # Jump the index forward past the repeated items

        return "\n".join(lines)

@dataclass
class PropertyValueRecord:
    offset: int
    size: int
    data: bytes
    property_value_id: int
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]
    # Known fields (first bytes of the record)
    record_type: Optional[int] = None  # First 4 bytes
    marker: Optional[int] = None  # Second 4 bytes
    # Unclaimed payload - the remainder after known fields
    unclaimed_payload: Optional[NestedUnclaimedData] = None

    def __str__(self):
        """
        Display PropertyValue with nested curation.
        Shows claimed fields first, then explicitly declares unclaimed payload.
        """
        lines = []
        
        # Header with property value ID
        parts = [f"PropertyValue ID:{format_int(self.property_value_id)}"]
        
        # Show known fields if available
        if self.record_type is not None:
            parts.append(f"Type:{format_int(self.record_type)}")
        if self.marker is not None:
            parts.append(f"Marker:{format_int(self.marker)}")
        
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references[:2]]
            parts.append(f"Strings:{','.join(strs)}")
        
        lines.append(" ".join(parts))
        
        # Show unclaimed payload if present
        if self.unclaimed_payload:
            lines.append("")  # Blank line for readability
            lines.append(str(self.unclaimed_payload))
        
        return "\n".join(lines)

@dataclass
class GenericRecord:
    offset: int
    size: int
    data: bytes
    string_references: List[tuple]  # [(offset_in_record, string_table_offset, resolved_string)]

    def __str__(self):
        """Generates a detailed, multi-line summary of the record's content."""
        # --- Build the primary header line ---
        header_parts = []
        if self.string_references:
            strs = [f'"{r[2]}"' for r in self.string_references]
            header_parts.append(f"Strings: {','.join(strs)}")

        lines = [" ".join(header_parts)]
        lines.append("Content (summarized as 32-bit integers):")

        # --- Generate the integer array summary ---
        data = self.data
        padding = len(data) % 4
        if padding != 0:
            data += b'\x00' * (4 - padding)

        if not data:
            # If there's no data, just return the header string
            return " ".join(header_parts)

        int_array = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]

        # This logic iterates through the integers, summarizing runs of identical values
        # and annotating integers that correspond to known string references.
        summary_lines = []
        i = 0
        while i < len(int_array):
            num = int_array[i]

            # Find how many times this number repeats consecutively
            j = i + 1
            while j < len(int_array) and int_array[j] == num:
                j += 1
            repeat_count = j - i

            # Check if this integer's byte offset corresponds to a string reference
            string_annotation = ""
            byte_offset_start = i * 4
            byte_offset_end = byte_offset_start + 4
            for str_offset, _, resolved_str in self.string_references:
                if byte_offset_start <= str_offset < byte_offset_end:
                    string_annotation = f' [="{resolved_str}"]'
                    break

            # Format the output line
            line = f"- Index[{i:03d}]: {num} (0x{num:x}){string_annotation}"
            if repeat_count > 1:
                line += f" (repeats {repeat_count} times)"
            summary_lines.append(line)

            i = j  # Jump the index forward past the repeated items

        lines.extend(summary_lines)
        return "\n".join(lines)

def _generate_diff(expected: bytes, actual: bytes) -> List[str]:
    """Helper to generate a simple hex diff."""
    diff_lines = []
    for i in range(0, len(expected), 16):
        exp_chunk = expected[i:i+16]
        act_chunk = actual[i:i+16]
        if exp_chunk != act_chunk:
            diff_lines.append(f"    {i:04x}:")
            diff_lines.append(f"      - Expected: {' '.join(f'{b:02x}' for b in exp_chunk)}")
            diff_lines.append(f"      - Actual:   {' '.join(f'{b:02x}' for b in act_chunk)}")
    return diff_lines

@dataclass
class GeometryManagerRecord:
    """
    Parses the multi-part structure for schematic metadata records.
    This record has stable Config and Footer blocks, with a variable Payload.
    """
    offset: int
    data: bytes

    # Parsed sub-records
    padding: bytes
    config: bytes
    payload: bytes
    footer: bytes
    
    # Class-level constants for assertion
    EXPECTED_CONFIG = bytes.fromhex("0800000003000000")
    EXPECTED_FOOTER = bytes.fromhex("000000c802000000e8001a03")  # Based on sch5.oa

    def __str__(self):
        lines = [f"Geometry Manager Record (Size: {len(self.data)} bytes)"]
        
        # 1. Analyze Padding - Its size is its primary interpretation
        lines.append(f"  - Padding: {len(self.padding)} bytes")

        # 2. Analyze Config Block - Assert or Show Data
        if self.config == self.EXPECTED_CONFIG:
            lines.append(f"  - Config: 8 bytes (OK, matches expected pattern)")
        else:
            lines.append(f"  - Config: 8 bytes (MODIFIED - VIOLATES EXPECTED PATTERN)")
            # MANDATORY: Show the claimed data that does not match
            lines.extend(_generate_diff(self.EXPECTED_CONFIG, self.config))

        # 3. Analyze Payload - Interpret and Show All Data
        payload_ints_str = "empty"
        if self.payload:
            payload_ints = [f"0x{v:x}" for v in struct.unpack(f'<{len(self.payload)//4}I', self.payload)]
            payload_ints_str = f"{{{', '.join(payload_ints)}}}"
        lines.append(f"  - Payload: {len(self.payload)} bytes, Values: {payload_ints_str}")

        # 4. Analyze Footer - Assert or Show Data
        if self.footer == self.EXPECTED_FOOTER:
            lines.append(f"  - Footer: 12 bytes (OK, matches expected pattern)")
        else:
            lines.append(f"  - Footer: 12 bytes (MODIFIED - VIOLATES EXPECTED PATTERN)")
            # MANDATORY: Show the claimed data that does not match
            lines.extend(_generate_diff(self.EXPECTED_FOOTER, self.footer))

        return "\n".join(lines)

@dataclass
class ComponentPropertyRecord:
    """
    Parses the 132-byte structure that appears to define a component property.
    This structure has a static header and a dynamic value ID at the end.
    """
    offset: int
    data: bytes  # The raw 132 bytes

    # Parsed fields
    structure_id: int
    config_and_pointers: bytes
    padding: bytes
    value_id: int

    # Assertion results
    config_matches: bool
    padding_matches: bool

    # Class-level constants for expected patterns
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

    def __str__(self):
        lines = [
            f"Component Property Record (132 bytes)",
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
            
            # Get the parsed header to access offsets
            header_region = self.curator.regions[0] if self.curator.regions else None
            if not header_region or not isinstance(header_region.parsed_value, TableHeader):
                # Fallback to legacy parsing if header parsing failed
                return self._parse_legacy_fallback(header_end)
            
            header = header_region.parsed_value
            
            # PASS 2: Determine timestamp location using FIXED OFFSET from END
            # *** CRITICAL DISCOVERY ***
            # The timestamp separator is ALWAYS at exactly 20 bytes from the END of table 0xc
            # This holds true for ALL observed .oa files (sch_old.oa through sch18.oa)
            # 
            # Table structure:
            #   [Header: 716 bytes]
            #   [Variable data]
            #   [Timestamp separator: 16 bytes at offset (table_size - 20)]
            #   [Final data: 4 bytes]
            #
            # This eliminates the need to scan for separators to find the timestamp!
            timestamp_offset = None
            timestamp_val = None
            
            TIMESTAMP_OFFSET_FROM_END = 20
            if len(self.data) >= TIMESTAMP_OFFSET_FROM_END + 16:
                candidate_timestamp_offset = len(self.data) - TIMESTAMP_OFFSET_FROM_END
                # Verify it's actually a separator with a valid timestamp
                sep_info = self._check_separator(candidate_timestamp_offset)
                if sep_info:
                    pos, val = sep_info
                    ts_32bit = val & 0xFFFFFFFF
                    if ts_32bit > 946684800:
                        try:
                            datetime.datetime.utcfromtimestamp(ts_32bit)
                            timestamp_offset = pos
                            timestamp_val = val
                        except (ValueError, OSError):
                            pass
            
            # PASS 3: Use POINTER-DRIVEN parsing with header offsets
            # This significantly reduces diff noise by using stable boundaries
            return self._parse_pointer_driven(header, header_end, timestamp_offset, timestamp_val)

        except Exception:
            pass

        return self.curator.get_regions()

    def _parse_header_with_curator(self) -> int:
        """Parse header using BinaryCurator, treating it as a struct with named fields."""
        if len(self.data) < 16:
            return 0

        header_id = struct.unpack_from('<I', self.data, 0)[0]
        end_offset = struct.unpack_from('<I', self.data, 8)[0]

        if end_offset > len(self.data) or end_offset < 8:
            return 0

        # Read all pointer/value fields
        all_fields = [struct.unpack_from('<Q', self.data, i)[0] for i in range(8, end_offset, 8)]
        
        # Parse as struct with named fields
        # Field [0]: first_record_offset (always 0x2cc)
        first_record_offset = all_fields[0] if len(all_fields) > 0 else 0
        
        # Fields [1-30]: Unknown offsets
        unknown_offsets_1_30 = all_fields[1:31] if len(all_fields) > 31 else (all_fields[1:] if len(all_fields) > 1 else [])
        
        # Fields [31-33]: Boundary offsets (verified to be true offsets)
        boundary_offsets_31_33 = all_fields[31:34] if len(all_fields) > 33 else (all_fields[31:] if len(all_fields) > 31 else [])
        
        # Fields [34+]: Config values
        config_values = all_fields[34:] if len(all_fields) > 34 else []

        self.curator.claim(
            "Table Header",
            end_offset,
            lambda d: TableHeader(
                header_id=header_id,
                pointer_list_end_offset=end_offset,
                first_record_offset=first_record_offset,
                unknown_offsets_1_30=unknown_offsets_1_30,
                boundary_offsets_31_33=boundary_offsets_31_33,
                config_values=config_values,
                raw_all_fields=all_fields
            )
        )

        return end_offset

        return end_offset
    
    def _parse_pointer_driven(self, header: TableHeader, header_end: int, timestamp_offset: Optional[int], timestamp_val: Optional[int]) -> List[Region]:
        """
        Pointer-driven parsing using header offsets to define record boundaries.
        This reduces diff noise by using stable boundaries from the header.
        """
        # Extract valid offsets from header (only those that point into data region)
        candidate_offsets = []
        for offset in header.offsets:
            # Only include offsets that point into the data region after header
            if header_end <= offset < len(self.data):
                candidate_offsets.append(offset)
        
        # Remove duplicates and sort
        candidate_offsets = sorted(set(candidate_offsets))
        
        if not candidate_offsets:
            # No valid offsets, fall back to legacy parsing
            return self._parse_legacy_fallback(header_end, timestamp_offset, timestamp_val)
        
        # Filter offsets to keep only those that are well-separated
        # This prevents creating tiny records that break PropertyValue detection
        MIN_RECORD_SIZE = 32  # Minimum size for PropertyValue detection
        valid_offsets = [candidate_offsets[0]]  # Always keep first offset
        
        for offset in candidate_offsets[1:]:
            if offset - valid_offsets[-1] >= MIN_RECORD_SIZE:
                valid_offsets.append(offset)
        
        # Parse records using pointer boundaries
        for i in range(len(valid_offsets)):
            start_offset = valid_offsets[i]
            
            # Determine end of this record
            if i + 1 < len(valid_offsets):
                end_offset = valid_offsets[i + 1]
            else:
                # Last record
                end_offset = len(self.data)
            
            # Check if timestamp falls within this record's range
            # If so, limit the record to end before the timestamp
            if timestamp_offset and start_offset < timestamp_offset < end_offset:
                end_offset = timestamp_offset
            
            record_size = end_offset - start_offset
            if record_size <= 0:
                continue
            
            # Dispatch and claim this record
            self._dispatch_and_claim_pointer_record(start_offset, record_size, timestamp_offset, timestamp_val)
        
        # Claim timestamp if it exists and hasn't been claimed yet
        if timestamp_offset:
            # Find where timestamp should be claimed
            last_claimed_offset = valid_offsets[-1] if valid_offsets else header_end
            
            # Find the last valid offset before timestamp
            last_before_ts = header_end
            for off in valid_offsets:
                if off < timestamp_offset:
                    last_before_ts = off
                else:
                    break
            
            # Check if there's a gap between last offset and timestamp
            # This can happen if timestamp is not pointed to by header
            if timestamp_offset > last_before_ts:
                # The timestamp block should extend from the last pointer to the timestamp
                # But we may have already claimed it in the loop above
                # Let's check if we need to claim the timestamp specifically
                
                # Just claim the timestamp directly
                self.curator.seek(timestamp_offset)
                self.curator.claim(
                    "Timestamp",
                    16,
                    lambda d, v=timestamp_val: TimestampRecord(timestamp_offset, v)
                )
                
                # Claim any remaining data after timestamp
                remaining_start = timestamp_offset + 16
                if remaining_start < len(self.data):
                    remaining_size = len(self.data) - remaining_start
                    if remaining_size > 0:
                        self._claim_generic_or_property(remaining_start, remaining_size)
        
        return self.curator.get_regions()
    
    def _dispatch_and_claim_pointer_record(self, offset: int, size: int, timestamp_offset: Optional[int], timestamp_val: Optional[int]):
        """
        Dispatch and claim a record defined by header pointer boundaries.
        NOTE: Timestamp is handled separately, not in this method.
        """
        if size <= 0:
            return
        
        # No timestamp handling here - it's done in _parse_pointer_driven
        self._claim_record_segment(offset, size)
    
    def _claim_record_segment(self, offset: int, size: int):
        """Claim a record segment, checking for known patterns."""
        if size <= 0:
            return
        
        self.curator.seek(offset)
        
        # Check for separator
        if size >= 16:
            sep_info = self._check_separator(offset)
            if sep_info:
                cursor_pos, value_64 = sep_info
                self.curator.claim(
                    "Separator",
                    16,
                    lambda d, p=cursor_pos, v=value_64: SeparatorRecord(p, v)
                )
                # Claim remaining if any
                if size > 16:
                    self._claim_record_segment(offset + 16, size - 16)
                return
        
        # Check for NetUpdate
        if size >= 12:
            record_data = self.data[offset:offset + size]
            t = struct.unpack_from('<I', record_data, 0)[0]
            if t == 19 and len(record_data) >= 12:
                s1, s2 = struct.unpack_from('<II', record_data, 4)
                if s1 == s2 and s1 > 0:
                    payload_size = s1
                    full_size = 12 + payload_size
                    rem = full_size % 4
                    aligned_size = full_size + (4 - rem if rem != 0 else 0)
                    
                    if aligned_size <= size:
                        # Claim as NetUpdate
                        net_size = self._try_claim_net_update(offset)
                        if net_size > 0:
                            # Claim remaining if any
                            if size > net_size:
                                self._claim_record_segment(offset + net_size, size - net_size)
                            return
        
        # Check for padding
        if size >= 16:
            pad_size = self._try_claim_padding(offset)
            if pad_size > 0 and pad_size <= size:
                # Claim remaining if any
                if size > pad_size:
                    self._claim_record_segment(offset + pad_size, size - pad_size)
                return
        
        # Default: claim as property value or generic
        self._claim_generic_or_property(offset, size)

    def _dispatch_and_claim_record(self, offset: int, size: int, timestamp_offset: Optional[int], timestamp_val: Optional[int]):
        """
        Dispatch and claim a record based on its content.
        This method identifies the record type and claims it appropriately.
        Handles timestamp separators within larger blocks.
        """
        if size <= 0:
            return
        
        # Check if the timestamp is within this block
        if timestamp_offset is not None and offset <= timestamp_offset < offset + size:
            # Split the block at the timestamp
            before_size = timestamp_offset - offset
            after_size = offset + size - (timestamp_offset + 16)
            
            # Claim data before timestamp
            if before_size > 0:
                self._dispatch_simple_record(offset, before_size)
            
            # Claim timestamp
            self.curator.seek(timestamp_offset)
            self.curator.claim(
                "Timestamp",
                16,
                lambda d, v=timestamp_val: TimestampRecord(timestamp_offset, v)
            )
            
            # Claim data after timestamp
            if after_size > 0:
                self._dispatch_simple_record(timestamp_offset + 16, after_size)
            
            return
        
        # No timestamp in this block, use simple dispatch
        self._dispatch_simple_record(offset, size)
    
    def _dispatch_simple_record(self, offset: int, size: int):
        """Dispatch and claim a single record without timestamp handling."""
        if size <= 0:
            return
        
        record_data = self.data[offset:offset + size]
        
        self.curator.seek(offset)
        
        # Check if this is a separator (but not timestamp, already handled)
        if size >= 16:
            sep_info = self._check_separator(offset)
            if sep_info:
                cursor_pos, value_64 = sep_info
                self.curator.claim(
                    "Separator",
                    16,
                    lambda d, p=cursor_pos, v=value_64: SeparatorRecord(p, v)
                )
                # Claim remaining data in this block if any
                if size > 16:
                    remaining_size = size - 16
                    self.curator.seek(offset + 16)
                    self._claim_generic_or_property(offset + 16, remaining_size)
                return
        
        # Check if this is a NetUpdate record
        if size >= 12:
            net_size = self._try_claim_net_update(offset)
            if net_size > 0 and net_size <= size:
                # Claim remaining data if any
                if size > net_size:
                    remaining_size = size - net_size
                    self.curator.seek(offset + net_size)
                    self._claim_generic_or_property(offset + net_size, remaining_size)
                return
        
        # Check if this is padding
        if size >= 16:
            pad_size = self._try_claim_padding(offset)
            if pad_size > 0 and pad_size <= size:
                # Claim remaining data if any
                if size > pad_size:
                    remaining_size = size - pad_size
                    self.curator.seek(offset + pad_size)
                    self._claim_generic_or_property(offset + pad_size, remaining_size)
                return
        
        # Default: claim as property value or generic record
        self._claim_generic_or_property(offset, size)
    
    def _claim_generic_or_property(self, offset: int, size: int):
        """
        Scans a block of data for ComponentPropertyRecord structures.
        Any data surrounding these structures is claimed as generic or property value.
        """
        if size <= 0:
            return

        magic_number = b'\xa4\x00\x00\x00\x00\x00\x00\x00'
        struct_size = 132

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
                        data=rd,
                        structure_id=struct.unpack_from('<Q', rd, 0)[0],
                        config_and_pointers=rd[8:96],
                        padding=rd[96:128],
                        value_id=struct.unpack_from('<I', rd, 128)[0],
                        config_matches=(rd[8:96] == ComponentPropertyRecord.EXPECTED_CONFIG),
                        padding_matches=(rd[96:128] == ComponentPropertyRecord.EXPECTED_PADDING)
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

    def _check_and_claim_geometry_manager(self, offset: int, size: int) -> bool:
        """
        Checks if a data block is a GeometryManagerRecord and claims it.
        Returns True if claimed, False otherwise.
        """
        # Signature: 8-byte config + 12-byte footer
        CONFIG_SIG = GeometryManagerRecord.EXPECTED_CONFIG
        FOOTER_SIG = GeometryManagerRecord.EXPECTED_FOOTER
        MIN_SIZE = len(CONFIG_SIG) + len(FOOTER_SIG)  # Must be at least 20 bytes

        if size < MIN_SIZE:
            return False

        record_data = self.data[offset : offset + size]
        
        # The signature is not at a fixed position due to variable padding.
        # We find the config block, then check if the footer exists at the end.
        config_pos = record_data.find(CONFIG_SIG)
        
        # Check if config is present and footer is at the end of the block
        if config_pos != -1 and record_data.endswith(FOOTER_SIG):
            
            payload_start = config_pos + len(CONFIG_SIG)
            payload_end = size - len(FOOTER_SIG)
            
            # Ensure boundaries are logical
            if payload_start <= payload_end:
                padding = record_data[:config_pos]
                config = record_data[config_pos:payload_start]
                payload = record_data[payload_start:payload_end]
                footer = record_data[payload_end:]
                
                self.curator.seek(offset)
                self.curator.claim(
                    "GeometryManagerRecord",
                    size,
                    lambda d: GeometryManagerRecord(
                        offset=offset,
                        data=record_data,
                        padding=padding,
                        config=config,
                        payload=payload,
                        footer=footer
                    )
                )
                return True
        
        return False

    def _claim_as_generic_or_property_value(self, offset, size):
        """Helper to claim a chunk as either a PropertyValue or a GenericRecord."""
        if size <= 0:
            return

        # --- THE REFACTOR ---
        # 1. Try to claim as the new, specific GeometryManagerRecord FIRST.
        if self._check_and_claim_geometry_manager(offset, size):
            return  # Success, we are done.

        # --- The rest of the function remains the same ---
        record_data = self.data[offset : offset + size]
        property_value_info = self._check_property_value(record_data)
        
        self.curator.seek(offset)
        string_refs = self._find_string_refs_in_data(record_data)
        
        if property_value_info is not None:
            # Claim as PropertyValue
            self.curator.claim(
                "PropertyValue",
                size,
                lambda d, p=offset, s=size, rd=record_data, info=property_value_info, sr=string_refs:
                    PropertyValueRecord(
                        offset=p,
                        size=s,
                        data=rd,
                        property_value_id=info['property_value_id'],
                        string_references=sr,
                        record_type=info['record_type'],
                        marker=info['marker'],
                        unclaimed_payload=info['unclaimed_payload']
                    )
            )
        else:
            # Fallback to a GenericRecord
            self.curator.claim(
                "Generic",
                size,
                lambda d, p=offset, s=size, rd=record_data, sr=string_refs:
                    GenericRecord(p, s, rd, sr)
            )
    
    def _parse_legacy_fallback(self, header_end: int, timestamp_offset: Optional[int] = None, timestamp_val: Optional[int] = None) -> List[Region]:
        """Legacy parsing method as fallback."""
        # If timestamp wasn't provided, try to find it by scanning
        if timestamp_offset is None:
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
            timestamp_value = None
            for pos, val in reversed(separator_positions):
                ts_32bit = val & 0xFFFFFFFF
                if ts_32bit > 946684800:
                    try:
                        datetime.datetime.utcfromtimestamp(ts_32bit)
                        timestamp_pos = pos
                        timestamp_value = val
                        break
                    except (ValueError, OSError):
                        continue
            
            timestamp_offset = timestamp_pos
            timestamp_val = timestamp_value

        # PASS 3: Claim all structures with timestamp marked
        cursor = header_end
        while cursor < len(self.data):
            initial_cursor = cursor

            # Try separator
            sep_info = self._check_separator(cursor)
            if sep_info:
                cursor_pos, value_64 = sep_info
                self.curator.seek(cursor)
                if cursor == timestamp_offset:
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

            # Try to identify and claim property values or generic records
            # If we can't identify it as a property value, claim as generic
            claimed_size = self._try_claim_property_or_generic(cursor)
            if claimed_size > 0:
                cursor += claimed_size
                continue

            # Fallback to prevent infinite loops for completely unrecognized data
            if cursor == initial_cursor:
                # This case should ideally not be hit if generic records handle all leftovers
                unclaimed_size = self._find_next_record_start(cursor + 4) - cursor
                if unclaimed_size <= 0:
                    unclaimed_size = 4  # Default skip

                # We can either leave it unclaimed or create a "Raw" record
                # For now, just advance past it to avoid getting stuck
                cursor += unclaimed_size
                if cursor >= len(self.data):
                    break
        
        return self.curator.get_regions()

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

    def _find_next_record_start(self, start_offset):
        """Find the start of the next known record type to determine the end of the current one."""
        cursor = start_offset
        while cursor < len(self.data) - 4:
            # Check for separator or net update markers
            val = struct.unpack_from('<I', self.data, cursor)[0]
            if val == 0xffffffff or val == 19:
                return cursor
            cursor += 4
        return len(self.data)

    def _try_claim_property_or_generic(self, cursor) -> int:
        """
        Try to claim a property value. If that fails, claim a generic record.
        This ensures that no data between known records is left unclaimed.
        """
        # Determine the boundary of this potential record by finding the start of the *next* one.
        # The search must start after the beginning of the current potential record.
        end = self._find_next_record_start(cursor + 4)
        size = end - cursor
        if size <= 0:
            return 0

        record_data = self.data[cursor:end]

        # First, attempt to identify it as a PropertyValueRecord
        property_value_info = self._check_property_value(record_data)

        self.curator.seek(cursor)
        string_refs = self._find_string_refs_in_data(record_data)

        if property_value_info is not None:
            # It's a known property value
            self.curator.claim(
                "PropertyValue",
                size,
                lambda d, p=cursor, s=size, rd=record_data, info=property_value_info, sr=string_refs:
                    PropertyValueRecord(
                        offset=p,
                        size=s,
                        data=rd,
                        property_value_id=info['property_value_id'],
                        string_references=sr,
                        record_type=info['record_type'],
                        marker=info['marker'],
                        unclaimed_payload=info['unclaimed_payload']
                    )
            )
        else:
            # Fallback to a GenericRecord
            self.curator.claim(
                "Generic",
                size,
                lambda d, p=cursor, s=size, rd=record_data, sr=string_refs:
                    GenericRecord(p, s, rd, sr)
            )

        return size

    def _check_property_value(self, data: bytes) -> Optional[dict]:
        """
        Checks for a very specific Property Value record pattern.
        This record must start with 19, have a marker at index 1, and be of a certain size.
        Returns a dict with parsed info if it matches, None otherwise.
        """
        num_ints = len(data) // 4
        if num_ints < 8:
            return None

        record_type = struct.unpack_from('<I', data, 0)[0]
        marker = struct.unpack_from('<I', data, 4)[0]

        # This is the specific signature of the records the test expects to find.
        if record_type == 19 and marker == 0xc8000000:
            val_at_index_7 = struct.unpack_from('<I', data, 7 * 4)[0]
            if 20 < val_at_index_7 < 200:
                # We understand the first 32 bytes (8 integers)
                # The rest is unclaimed payload
                known_size = 32
                unclaimed_bytes = data[known_size:] if len(data) > known_size else b''
                
                return {
                    'property_value_id': val_at_index_7,
                    'record_type': record_type,
                    'marker': marker,
                    'unclaimed_payload': NestedUnclaimedData(
                        label="UNCLAIMED PAYLOAD",
                        data=unclaimed_bytes,
                        description=f"Unknown data within PropertyValueRecord (after first 32 bytes)"
                    ) if unclaimed_bytes else None
                }

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
