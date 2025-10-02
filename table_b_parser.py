# table_b_parser.py - Focused parser for property list table 0xb
import struct
from oaparser import BinaryCurator

class TableBParser:
    """
    Parses Table 0xb based on the hypothesis that it contains a header,
    a record count, and a list of property records.

    Structure Hypothesis:
    - Header: 220 bytes (0xDC), contents not fully parsed.
    - Record Count: 4-byte little-endian uint at offset 0xDC.
    - Record List: An array of 4-byte records following the count.
    """

    def __init__(self, data):
        self.data = data
        self.records = []

    def parse(self):
        """
        Parses the table data according to the structured hypothesis.
        Returns a formatted string summary of the parsed data.
        """
        if len(self.data) < 224:  # header_size + count_offset
            return f"Table 0xb: Too small ({len(self.data)} bytes)"
        
        curator = BinaryCurator(self.data)
        
        # Claim the 220-byte header (currently opaque)
        curator.claim("Header (opaque block)", 220, lambda d: "Content not yet fully understood")
        
        # Claim the record count
        record_count = struct.unpack_from('<I', self.data, 220)[0]
        curator.claim("Record Count", 4, lambda d: f"{struct.unpack('<I', d)[0]} records")
        
        # Claim each 4-byte record
        expected_records = min(record_count, (len(self.data) - 224) // 4)
        
        for i in range(expected_records):
            offset = 224 + (i * 4)
            record_val = struct.unpack_from('<I', self.data, offset)[0]
            val_low = record_val & 0xFFFF
            val_high = (record_val >> 16) & 0xFFFF
            
            curator.seek(offset)
            curator.claim(
                f"Property Record[{i}]",
                4,
                lambda d, v=record_val, l=val_low, h=val_high: 
                    f"0x{v:08x} (Low=0x{l:04x}, High=0x{h:04x})"
            )
            
            # Store the parsed record for potential external use
            self.records.append({
                "index": i,
                "offset": offset,
                "full_value": record_val,
                "low_word": val_low,
                "high_word": val_high
            })
        
        # Generate report
        lines = [f"Table 0xb (Property List): {len(self.data)} bytes"]
        lines.append("="*80)
        lines.append("")
        lines.append(curator.report())
        
        if record_count > expected_records:
            lines.append("")
            lines.append(f"[WARNING] Record count indicates {record_count} records, but only {expected_records} could be read")
        
        return "\n".join(lines)
