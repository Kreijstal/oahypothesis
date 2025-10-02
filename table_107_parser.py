# table_107_parser.py
"""
Specialized parser for Table 0x107 (Object Edit Metadata).

This parser encapsulates all logic for interpreting Table 0x107. It uses the
BinaryCurator internally to produce a complete, lossless list of claimed and
unclaimed data regions for the entire table.
"""

import struct
from dataclasses import dataclass
from typing import List, Optional

from oaparser import BinaryCurator, Region

# --- Data Structures (Models for Parsed Data) ---

@dataclass
class ObjectEditRecord:
    """
    Represents a single piece of identified metadata within Table 0x107.
    This object is stored in a ClaimedRegion's `parsed_value` field.
    """
    record_type: str
    description: str
    offset: int
    size: int
    raw_value: int
    string_index: Optional[int] = None
    resolved_name: Optional[str] = None

    def __str__(self) -> str:
        """Renders this single record for the final report."""
        result = f"Type: {self.record_type}, Value: {self.raw_value} (0x{self.raw_value:x})"
        if self.string_index is not None:
            result += f", String[{self.string_index}]: '{self.resolved_name or '???'}'"
        return result

# --- The Parser Class ---

class Table107Parser:
    """
    Parser for Table 0x107 (Object Edit Metadata).
    
    Uses BinaryCurator internally to track claimed and unclaimed regions.
    Returns a list of Region objects representing the complete table structure.
    """
    
    def __init__(self, data: bytes, string_list: Optional[List[str]] = None):
        if not isinstance(data, bytes):
            raise TypeError("Input data must be bytes.")
        self.data = data
        self.string_list = string_list if string_list else []
        # The curator is now an internal implementation detail of this parser.
        self.curator = BinaryCurator(self.data)

        # Schema of known data structures within this table.
        self.KNOWN_RECORDS_SCHEMA = [
            ("R0/V0 Instance Name", 0x2b9, 1, self._parse_name_pointer),
            ("C0 Instance Name", 0x2c1, 1, self._parse_name_pointer),
            ("R0/V0 Edit Count", 0x2e8, 4, self._parse_version_counter),
        ]

    def _decode_name_pointer_value(self, value: int) -> Optional[int]:
        """Converts a raw byte value into a string table index."""
        if value < 1 or (value - 1) % 2 != 0:
            return None
        return ((value - 1) // 2) + 64

    # --- Parser Functions for `claim()` ---
    # These functions take raw bytes and return the rich data object.

    def _parse_name_pointer(self, raw_bytes: bytes, desc: str, offset: int) -> ObjectEditRecord:
        """Parser function for claiming a component name pointer."""
        raw_val = raw_bytes[0]
        record = ObjectEditRecord(
            record_type="Name Pointer",
            description=desc,
            offset=offset,
            size=1,
            raw_value=raw_val
        )
        record.string_index = self._decode_name_pointer_value(record.raw_value)
        if record.string_index is not None and 0 <= record.string_index < len(self.string_list):
            record.resolved_name = self.string_list[record.string_index]
        return record

    def _parse_version_counter(self, raw_bytes: bytes, desc: str, offset: int) -> ObjectEditRecord:
        """Parser function for claiming a version/edit counter."""
        raw_val = struct.unpack('<I', raw_bytes)[0]
        return ObjectEditRecord(
            record_type="Version Counter",
            description=desc,
            offset=offset,
            size=4,
            raw_value=raw_val
        )

    def parse(self) -> List[Region]:
        """
        Parse Table 0x107 and return a list of regions.
        
        Returns:
            List of Region objects (ClaimedRegion and UnclaimedRegion) representing
            the complete structure of the table, including all unclaimed bytes.
        """
        # Claim all known structures in the table
        for description, offset, size, parser_func in self.KNOWN_RECORDS_SCHEMA:
            if offset + size <= len(self.data):
                self.curator.seek(offset)
                # Create a closure that captures the current values
                def make_claim_parser(pf, desc, off):
                    def claim_parser(raw_bytes):
                        return pf(raw_bytes, desc, off)
                    return claim_parser
                
                self.curator.claim(
                    description,
                    size,
                    make_claim_parser(parser_func, description, offset)
                )

        # Return the complete list of regions (claimed and unclaimed)
        # This ensures no data is hidden - all unclaimed bytes will be visible
        return self.curator.get_regions()
