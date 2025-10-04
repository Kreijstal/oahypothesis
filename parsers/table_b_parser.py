# table_b_parser.py - Focused parser for property list table 0xb
import struct
from typing import List
from oaparser import BinaryCurator, Region

class TableBParser:
    """
    Parses Table 0xb based on the hypothesis that it contains a header,
    a record count, and a list of property records.

    Structure Hypothesis:
    - Header: 220 bytes (0xDC), contents not fully parsed.
    - Record Count: 4-byte little-endian uint at offset 0xDC.
    - Record List: An array of 4-byte records following the count.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.records = []
        self.curator = BinaryCurator(self.data)

    def parse(self) -> List[Region]:
        """
        Parses the table data and returns regions.
        """
        if len(self.data) < 224:  # header_size + count_offset
            return self.curator.get_regions()
        
        # Don't claim the 220-byte header since we don't understand it - leave it unclaimed
        # Skip past it to claim the record count
        self.curator.seek(220)
        
        # Claim the record count
        record_count = struct.unpack_from('<I', self.data, 220)[0]
        self.curator.claim("RecordCount", 4, lambda d: f"{struct.unpack('<I', d)[0]} records")
        
        # Claim each 4-byte record
        expected_records = min(record_count, (len(self.data) - 224) // 4)
        
        for i in range(expected_records):
            offset = 224 + (i * 4)
            record_val = struct.unpack_from('<I', self.data, offset)[0]
            val_low = record_val & 0xFFFF
            val_high = (record_val >> 16) & 0xFFFF
            
            self.curator.seek(offset)
            self.curator.claim(
                f"Prop[{i}]",
                4,
                lambda d, v=record_val, l=val_low, h=val_high: 
                    f"0x{v:08x} (L:0x{l:04x} H:0x{h:04x})"
            )
            
            # Store the parsed record for potential external use
            self.records.append({
                "index": i,
                "offset": offset,
                "full_value": record_val,
                "low_word": val_low,
                "high_word": val_high
            })
        
        return self.curator.get_regions()
