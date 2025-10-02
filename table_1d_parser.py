# table_1d_parser.py - Parser for table directory 0x1d
import struct
from oaparser import BinaryCurator

class Table1dParser:
    """
    Parser for table 0x1d (Table Directory)
    
    This table contains an array of table IDs, acting as a directory
    or reference list of specific tables in the file.
    """
    
    def __init__(self, data):
        self.data = data
        self.table_ids = []
        
    def parse(self):
        """Parse the table directory with complete data dump"""
        if len(self.data) < 8:
            return f"Table Directory (0x1d): Too small ({len(self.data)} bytes)"
        
        curator = BinaryCurator(self.data)
        
        # Known table names for interpretation
        known_tables = {
            0x04: "Counter/Version",
            0x05: "Flag/Unused", 
            0x06: "Type/Count Pair",
            0x07: "Pointer Table",
            0x19: "Unknown Structure",
            0x1c: "Record Structure",
            0x1d: "Table Directory (self-reference)",
            0x25: "Unknown",
            0x2a: "Magic Number"
        }
        
        # Parse as array of 64-bit table IDs
        if len(self.data) % 8 == 0:
            num_entries = len(self.data) // 8
            
            for i in range(num_entries):
                # Parse this entry
                offset = i * 8
                table_id = struct.unpack('<Q', self.data[offset:offset+8])[0]
                self.table_ids.append(table_id)
                name = known_tables.get(table_id, "Unknown")
                
                curator.seek(offset)
                curator.claim(
                    f"Table ID [{i}]", 
                    8, 
                    lambda data, tid=table_id, n=name: f"Table 0x{tid:x} ({tid}) - {n}"
                )
        
        # Generate report
        lines = [f"Table Directory (0x1d): {len(self.data)} bytes"]
        lines.append("="*80)
        lines.append("")
        lines.append(curator.report())
        
        if len(self.data) % 8 != 0:
            lines.append("")
            lines.append(f"\nWarning: Size {len(self.data)} is not a multiple of 8")
            lines.append("Cannot fully parse as array of 64-bit values")
        
        return "\n".join(lines)
